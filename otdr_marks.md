# OTDR: метки обрывов в QGIS Server / QWC2

## Задача

`snmp_trap_receiver_frust.py` пишет SNMP-trap в `sasplanet_marks.otdr.events`
(`src_ip`, `refl_name`, `length_km`, `raw`). Нужно: опрашивать таблицу, для нового `id`
найти в проекте линейный слой с именем `refl_name`, пройти от начала трассы `route_m`
метров, поставить метку «красный крест 45°» с подписью `Обрыв!Время:гггг/ММ/дд/чч:мм:сс`,
показать её в QWC2 и сохранить в проекте QGIS.

## Плагин `otdr_marks` (1.1.0)

Репозиторий `https://github.com/Ultramiloserdie/ultravossoedinenie`,
ветка `claude/inspiring-mccarthy-wey7k8`, каталог `otdr_marks/`.

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
- Метки показывает PostGIS-слой `otdr.events` проекта. Его один раз добавляют в
  QGIS Desktop со стилем `otdr_marks/otdr_events.qml`: крест `cross`, угол 45°,
  красный; подпись `'Обрыв!Время:' || format_date("received_at", 'yyyy/MM/dd/HH:mm:ss')`.
- Проект плагин только читает. Если слоя `otdr.events` в проекте нет, в журнале
  QGIS Server предупреждение с тегом `OTDR`.
- Колонка статуса: `status` или `stasus` — находится любая.

Настройки — в начале `otdr_marks/otdr_marks.py`: `POLL_SEC`, `EVENTS_SRID`, `CABLE_FACTOR`,
`START_OFFSET_M`, `SNAP_TOL_M`, `ORDER_FIELD`.

Проверено: QGIS Server 3.34 (Ubuntu 24.04), PostgreSQL 16 / PostGIS 3.4, несколько
процессов FastCGI.

### Изменения 1.1.0

- Плагин больше не записывает проект. Версия 1.0.0 при старте добавляла слой
  «OTDR события» (или меняла источник имеющегося слоя `otdr.events` на
  `service='<OTDR_PG_SERVICE>'`) и перезаписывала проект в `public.qgis_projects`.
  Если QGIS Server не находит этот сервис при обработке запросов, весь проект
  отвечает `Layer(s) not valid` (HTTP 500) — см. «Проект не открывается».
- Стиль слоя меток — файл `otdr_events.qml`, автообновление — свойство слоя в проекте.
- `check_project.py`: проверка проекта в том виде, в каком его загружает QGIS Server.

## Установка и обновление

```bash
rm -rf /tmp/uv && git clone -b claude/inspiring-mccarthy-wey7k8 https://github.com/Ultramiloserdie/ultravossoedinenie /tmp/uv
sudo mkdir -p /opt/qgis-server/plugins
sudo rm -rf /opt/qgis-server/plugins/otdr_marks && sudo cp -r /tmp/uv/otdr_marks /opt/qgis-server/plugins/
sudo systemctl restart 'qgis-server@*.service'
```

## Слой меток в проекте (QGIS Desktop, один раз)

1. Открыть проект `q2s` из PostgreSQL.
2. Если слоя «OTDR события» нет: Браузер → PostgreSQL → подключение → `otdr` → `events`
   → добавить, переименовать в «OTDR события»; Свойства слоя → Стиль → «Загрузить стиль…» →
   `otdr_events.qml`. Слой, добавленный версией 1.0.0, оставить.
3. Свойства слоя → Отрисовка → «Периодическое обновление слоя»: 10 с, режим «Перезагрузить».
4. Сохранить проект.
5. Перезапустить QGIS Server: проект из БД процесс читает один раз и до перезапуска
   изменений не видит (GetCapabilities тоже кэшируется).

   ```bash
   sudo systemctl restart 'qgis-server@*.service'
   ```

6. Перегенерировать конфигурацию QWC: qwc-admin-gui → Generate service configuration,
   либо `curl -X POST "http://localhost:5010/generate_configs?tenant=default"`
   (qwc-config-generator в qwc-docker). При `permissions_default_allow=false` выдать
   права на слой «OTDR события».

Подключение слоя должно быть доступно QGIS Server при обработке запросов: то же, что у
остальных слоёв проекта, или сервис из `/etc/postgresql-common/pg_service.conf`.

## Автообновление в QWC2

- QWC2 перезапрашивает слой темы с интервалом «Периодическое обновление слоя» его
  подслоёв: qwc-config-generator берёт `autoRefreshTime` из проекта и пишет
  `refreshInterval` в `themes.json`.
- Нужны qwc-map-viewer и qwc-config-generator не старше v2025.05.07 (в 2025-lts нет,
  в 2026-lts есть). Проверка версий:

  ```bash
  docker ps --format '{{.Image}}' | grep -E 'qwc-map-viewer|qwc-config-generator'
  ```

  Скрипт `themesConfig.py`/`themesConfig.js` из qwc2 интервал не переносит.
- Задержка появления метки: до `POLL_SEC` (5 с) + интервал слоя.
- Нагрузка: каждый открытый клиент перерисовывает всю тему раз в интервал.

## Проект не открывается (`Layer(s) not valid`)

QGIS Server не отдаёт проект целиком, если не загружается хотя бы один слой
(кроме слоёв из «Свойства проекта → QGIS Server → WMS → Исключить слои» и при
`QGIS_SERVER_IGNORE_BAD_LAYERS=1`).
При обработке запроса окружение процесса — параметры FastCGI: переменных из unit
(`PGSERVICEFILE` и т.п.) нет, `pg_service.conf` ищется только в
`/etc/postgresql-common/` и `~www-data/.pg_service.conf`.

Проверка в таком же окружении:

```bash
sudo -u www-data env -i QT_QPA_PLATFORM=offscreen /usr/bin/python3 /opt/qgis-server/plugins/otdr_marks/check_project.py 'postgresql:?service=gisdb&schema=public&project=q2s'
```

- `Слоёв: N, не загружаются: 0` — проект для QGIS Server исправен.
- `definition of service "gisdb" not found` — сервис не виден при запросах: секция
  `[gisdb]` должна быть в `/etc/postgresql-common/pg_service.conf` (права
  `root:www-data`, `640`), затем перезапуск QGIS Server.
- Другой слой в списке «Не загружается» — исправить его источник в QGIS Desktop
  (ПКМ по слою → «Изменить источник данных…», у недоступного слоя — «Исправить источник
  данных…»), сохранить проект, перезапустить QGIS Server.

Временно открыть проект без незагружаемых слоёв:

```bash
echo 'QGIS_SERVER_IGNORE_BAD_LAYERS=1' | sudo tee -a /etc/qgis-server/env
sudo systemctl restart 'qgis-server@*.service'
```

## Переменные окружения

| Переменная | Значение |
|---|---|
| `QGIS_PLUGINPATH` | `/opt/qgis-server/plugins` |
| `OTDR_PG_SERVICE` | имя секции `[...]` из `pg_service.conf` (здесь `gisdb`) |
| `OTDR_PROJECT` | имя проекта в `public.qgis_projects` (здесь `q2s`); можно не задавать, если проект один |

`OTDR_PG_SERVICE` — сервис, по которому плагин подключается к `otdr.events` и читает проект.

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
Поэтому `PGSERVICEFILE` из unit libpq видит только до первого запроса, а слои проекта
загружаются уже при запросе. Фоновый поток плагина из-за этого терял переменные
процесса и читал освобождённую память — исправлено коммитом `4e5228f`: после каждого
ответа плагин возвращает окружение процесса.

## Замечания

- `route_m` при вставке пуст (SNMP-скрипт его не пишет) — расстояние из `length_km`,
  результат записывается в `route_m`; заранее заполненный `route_m` используется как есть.
- В референс-скрипте символ `x` с одним `color` рисуется цветом обводки (по умолчанию
  тёмно-серый), не красным; в `otdr_events.qml` задан `outline_color`.
- После каждого сохранения проекта в QGIS Desktop — перезапуск QGIS Server и
  перегенерация конфигурации QWC.
- Референс-скрипт в Desktop параллельно не запускать — событие обработает тот, кто
  заберёт его первым.
- Журнал: тег `OTDR` в логе QGIS Server появляется, когда процесс-опросчик обрабатывает
  запрос. Результат по каждому событию сразу виден в `otdr.events.status` / `note`.
