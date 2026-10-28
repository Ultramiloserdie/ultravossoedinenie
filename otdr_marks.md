# OTDR: метки обрывов в QGIS Server / QWC2

## Задача

`snmp_trap_receiver_frust.py` пишет SNMP-trap в `sasplanet_marks.otdr.events`
(`src_ip`, `refl_name`, `length_km`, `raw`). Нужно: опрашивать таблицу, для нового `id`
найти в проекте линейный слой с именем `refl_name`, пройти от начала трассы `route_m`
метров, поставить метку «красный крест 45°» с подписью `Обрыв!Время:гггг/ММ/дд/чч:мм:сс`,
показать её в QWC2 и сохранить в проекте QGIS.

## Плагин `otdr_marks`

Репозиторий `https://github.com/Ultramiloserdie/ultravossoedinenie`,
ветка `claude/qgis-snmp-trap-plugin-9t4s6k`, каталог `otdr_marks/`.

Как работает:

- Фоновый поток в одном процессе QGIS Server (выбор через абстрактный UNIX-сокет),
  опрос раз в 5 с, без зависимости от запросов к серверу. `QTimer` не годится:
  процесс FastCGI между запросами не обрабатывает события Qt.
- Забирает строки `status IS NULL` (`FOR UPDATE SKIP LOCKED`); `status = 'work'`
  старше 10 мин берётся заново.
- Ищет линейный слой проекта, имя (или таблица) которого совпадает с `refl_name`
  без учёта регистра.
- Расстояние: `route_m`, если заполнен; иначе `length_km × 1000` (с `CABLE_FACTOR`,
  `START_OFFSET_M`). Меряется по эллипсоиду, участки трассы сшиваются, кривые
  переводятся в отрезки.
- Пишет в `otdr.events`: `status` (`ok`/`error`), `processed_at`, `route_m`, `note`,
  `geom` (EPSG:3395).
- Метки показывает слой проекта «OTDR события» (PostGIS `otdr.events`): крест `cross`,
  угол 45°, красная обводка; подпись
  `'Обрыв!Время:' || format_date("received_at", 'yyyy/MM/dd/HH:mm:ss')`.
  Если слоя нет, плагин добавляет его и сохраняет проект в `public.qgis_projects`
  при старте.
- Колонка статуса: `status` или `stasus` — находится любая.

Настройки — в начале `otdr_marks/otdr_marks.py`: `POLL_SEC`, `EVENTS_SRID`, `LABEL_EXPR`,
`CABLE_FACTOR`, `START_OFFSET_M`, `SNAP_TOL_M`, `ORDER_FIELD`.

Проверено: QGIS Server 3.34 (Ubuntu 24.04), PostgreSQL 16 / PostGIS 3.4, несколько
процессов FastCGI. API сверено с QGIS 4.

## Установка

```bash
git clone -b claude/qgis-snmp-trap-plugin-9t4s6k https://github.com/Ultramiloserdie/ultravossoedinenie /tmp/uv
sudo mkdir -p /opt/qgis-server/plugins
sudo cp -r /tmp/uv/otdr_marks /opt/qgis-server/plugins/
```

Обновление:

```bash
cd /tmp/uv && git pull && sudo cp -r otdr_marks /opt/qgis-server/plugins/ && sudo systemctl restart 'qgis-server@*.service'
```

## Переменные окружения

| Переменная | Значение |
|---|---|
| `QGIS_PLUGINPATH` | `/opt/qgis-server/plugins` |
| `OTDR_PG_SERVICE` | имя секции `[...]` из `pg_service.conf` (здесь `gisdb`) |
| `OTDR_PROJECT` | имя проекта в `public.qgis_projects` (здесь `q2s`); можно не задавать, если проект один |

`OTDR_PG_SERVICE` — тот же сервис, что после `service=` в параметре `MAP` QGIS Server.
По нему плагин подключается к `otdr.events`, читает/сохраняет проект и задаёт источник
слоя «OTDR события».

Переменные должны быть в окружении процесса QGIS Server (unit systemd), а не в
`fastcgi_param` nginx: QGIS читает `QGIS_PLUGINPATH`, а плагин — `OTDR_*` один раз
при старте процесса, до первого запроса.

### На этом сервере: `qgis-server@.service` + `qgis-server@.socket`

Сокеты держит systemd (socket activation), spawn-fcgi нет. Unit-шаблон:

```ini
[Service]
User=www-data
Group=www-data
StandardInput=socket
StandardOutput=null
StandardError=journal
EnvironmentFile=/etc/qgis-server/env
ExecStart=/usr/lib/cgi-bin/qgis_mapserv.fcgi
Restart=always
```

**Способ 1 (проще): дописать в `/etc/qgis-server/env`** — формат `KEY=value`,
без `Environment=` и `[Service]`:

```bash
grep -n QGIS_PLUGINPATH /etc/qgis-server/env   # если уже есть — дописать путь через ":"
sudo tee -a /etc/qgis-server/env >/dev/null <<'EOF'
QGIS_PLUGINPATH=/opt/qgis-server/plugins
OTDR_PG_SERVICE=gisdb
OTDR_PROJECT=q2s
EOF
sudo systemctl restart 'qgis-server@*.service'
```

**Способ 2: drop-in** (без редактора):

```bash
sudo mkdir -p /etc/systemd/system/qgis-server@.service.d
sudo tee /etc/systemd/system/qgis-server@.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=gisdb
Environment=OTDR_PROJECT=q2s
EOF
sudo systemctl daemon-reload
sudo systemctl restart 'qgis-server@*.service'
```

Через редактор: `sudo systemctl edit qgis-server@.service`, строки — без `#`, между
`### Anything between here...` и `### Edits below this comment will be discarded`.
Сохранение: nano — Ctrl+O, Enter (имя временного файла не менять), Ctrl+X;
vim — Esc, `:wq`. Успех: «Successfully installed edited file ...».

Использовать один способ. При совпадении переменных приоритет у drop-in.

Автозапуск экземпляра после перезагрузки (иначе процесс и опрос стартуют только по
первому запросу):

```bash
systemctl is-enabled qgis-server@1.service
sudo systemctl enable qgis-server@1.service   # если не enabled
```

### Проверка

```bash
systemctl list-units --all 'qgis-server@*'
systemctl cat qgis-server@1.service
systemctl show qgis-server@1.service -p Environment
PID=$(systemctl show -p MainPID --value qgis-server@1.service)
sudo tr '\0' '\n' < /proc/$PID/environ | grep -E 'QGIS_PLUGINPATH|OTDR_'
```

`MainPID=0` — процесс не запущен (`sudo systemctl start qgis-server@1.service`).
Пусто при запущенном процессе — не было перезапуска после правки.
Для переменных из `/etc/qgis-server/env` `systemctl show -p Environment` их не покажет —
смотреть `/proc/$PID/environ`.

## pg_service.conf

Файл в общей папке Windows сервер Ubuntu не читает: libpq ищет его только локально.
Без `PGSERVICEFILE` места поиска:

- `/etc/postgresql-common/pg_service.conf`;
- `~/.pg_service.conf` пользователя из `User=` (`www-data` → `/var/www/.pg_service.conf`).

### Скопировать вручную

1. Windows: открыть `\\<хост>\<папка>\pg_service.conf` в Блокноте, Ctrl+A, Ctrl+C.
2. Сервер:

   ```bash
   sudo nano /etc/postgresql-common/pg_service.conf
   ```

   Вставить (PuTTY — правая кнопка мыши, Windows Terminal — Ctrl+Shift+V),
   Ctrl+O, Enter, Ctrl+X. Существующий файл дополнять, не затирать.
3. Проверить `host=` — адрес PostgreSQL, доступный с сервера (тот же сервер — `localhost`):

   ```bash
   sudo grep -nE '^\[|host=' /etc/postgresql-common/pg_service.conf
   ```

4. Права (в файле пароль):

   ```bash
   sudo chown root:www-data /etc/postgresql-common/pg_service.conf
   sudo chmod 640 /etc/postgresql-common/pg_service.conf
   sudo systemctl restart 'qgis-server@*.service'
   ```

Альтернатива: `smbclient //<хост>/<папка> -U <пользователь> -c 'get pg_service.conf /tmp/pg_service.conf'`,
затем `sudo install -o root -g www-data -m 640 /tmp/pg_service.conf /etc/postgresql-common/pg_service.conf`.

Монтировать Windows-папку и указывать `PGSERVICEFILE` не рекомендуется: зависимость от
сети и Windows-машины, порядок монтирования при загрузке; путь пришлось бы задавать
и в unit (`Environment=PGSERVICEFILE=...`), и в nginx (`fastcgi_param PGSERVICEFILE ...;`).

### Особенность FastCGI

QGIS Server принимает запросы через `FCGI_Accept` (libfcgi), который на время запроса
подменяет `environ` процесса параметрами запроса и освобождает их в начале следующего.
Поэтому `PGSERVICEFILE` из unit libpq видит только до первого запроса. Фоновый поток
плагина из-за этого терял переменные процесса и читал освобождённую память — исправлено
коммитом `4e5228f`: после каждого ответа плагин возвращает окружение процесса.

## После первого запуска (один раз)

1. `sudo systemctl restart 'qgis-server@*.service'` — все процессы перечитают проект
   с новым слоем.
2. Перегенерировать конфигурацию QWC: qwc-admin-gui → Generate service configuration,
   либо `curl -X POST "http://localhost:5010/generate_configs?tenant=default"`
   (qwc-config-generator в qwc-docker).
3. При `permissions_default_allow=false` выдать права на слой «OTDR события».

## Замечания

- `route_m` при вставке пуст (SNMP-скрипт его не пишет) — расстояние из `length_km`,
  результат записывается в `route_m`; заранее заполненный `route_m` используется как есть.
- В референс-скрипте символ `x` с одним `color` рисуется цветом обводки (по умолчанию
  тёмно-серый), не красным; в плагине задан `outline_color`.
- QWC2 карту сам не обновляет: метка появляется при следующей перерисовке (GetMap).
- Проект перезаписывает QGIS Server один раз; его версия должна быть не ниже версии
  QGIS Desktop, иначе пропадут неизвестные серверу свойства.
- Слой «OTDR события» использует `service=gisdb`: на ПК с QGIS Desktop в `pg_service.conf`
  нужен сервис с тем же именем.
- Существующий слой `otdr.events` (например, от референс-скрипта) не дублируется, а
  переоформляется.
- Референс-скрипт в Desktop параллельно не запускать — событие обработает тот, кто
  заберёт его первым.
- Журнал: тег `OTDR` в логе QGIS Server появляется, когда процесс-опросчик обрабатывает
  запрос. Результат по каждому событию сразу виден в `otdr.events.status` / `note`.
