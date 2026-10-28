# Стенограмма: плагин QGIS Server для меток обрывов OTDR

Сообщения пользователя и ответы ассистента в порядке диалога. Промежуточные служебные
действия ассистента (установка тестового стенда, запуск команд) опущены.

---

## 1. Пользователь

Скрипт "snmp_trap_receiver_frust.py" принимает SNMP-trap, фильтрует содержание OID, вычленяя значения src_ip, refl_name, length_km, Jsonb(raw) и передаёт их
на сервер PostgreSQL в схему otdr, таблицу events (база данных sasplanet_marks, содержащая две схемы (public и otdr)).
Таблица otdr.events содержит в себе следующие атрибуты (в скобках data type): "id"(bigint), "received_at"(timestamp with time zone), "src_ip"(inet), "refl_name"(text), "length_km"(double precision), "raw"(jsonb), "stasus"(text), "processed_at"(timestamp with time zone), "route_m"(double precision),
"note"(text), "geom"(geometry).

На Ubuntu Server 24.04 установлен QGIS Server с подключенным к нему PostgreSQL (БД sasplanet_marks под пользователем postgres, с заданным user и password в pg_serveice.conf). В этой БД, в схеме public сохранён проект QGIS, который просматривается с web-browser, через QWC2.
Нужен плагин для QGIS Server, который выполняет функционал: опрос таблицы -> при появлении нового id (primary key) обработать событие вычленив два значения refl_name и length_km -> сравнить название refl_name с именем слоя (перебрать слои всего проекта) -> при совпадении от начала отсчёта векторного объекта
пройти длину равную числовому значению в метрах из route_m (refl_name обязательно соответствует протяженному объекту векторной геометрии, например линия, мультилиния, мультикривая, кривая) -> поставить подписанную ("Обрыв!Время:год/месяц/день/время") метку (красный крест повернутый на 45 градусов) ->
(чтобы у клиента QuantumWebClient2(QWC2) отобразилось подписанное значение) -> Сохранить отображенную метку в проекте QGIS.

Референс скрипта отображения для QGIS Desktop:

```python
from datetime import datetime

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsDistanceArea,
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsGeometry,
    QgsMessageLog,
    QgsPalLayerSettings,
    QgsPointXY,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
    QgsMarkerSymbol
)
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface

if Qgis.QGIS_VERSION_INT >= 33800:
    from qgis.PyQt.QtCore import QMetaType
    _STR, _DBL = QMetaType.Type.QString, QMetaType.Type.Double
else:
    from qgis.PyQt.QtCore import QVariant
    _STR, _DBL = QVariant.String, QVariant.Double

# Дано
REFL_FIELD = "refl_name"    # поле с названием рефлектограммы; 
ORDER_FIELD = None          # поле порядка участков трассы; 
CABLE_FACTOR = 1.0          # оптическая длина волокна больше физической? 1.02-1.07?
START_OFFSET_M = 0.0        # волокно до начала трассы, м
SNAP_TOL_M = 5.0            # допуск стыковки участков, м
DEFAULT_ELLIPSOID = "EPSG:7030"

PG_CONNECTION = None        # имя подключения PostgreSQL из Браузера QGIS;
# None - параметры первого PostGIS-слоя проекта
EVENTS_TABLE = "otdr.events" # название таблицы в postgres, схема otdr
EVENTS_SRID = 3395           # SRID яндекса колонки geom в EVENTS_TABLE
EVENTS_LAYER = "OTDR события" # название слоя после создания в q
POLL_SEC = 5                    # опрос таблицы
MARK_LAYER = "OTDR_метки"   # слой для ручного locate(): существующий или временный

_TIMER = "otdr_poll_timer"
_CLAIM = """ UPDATE {t} SET status = 'work'
WHERE id IN (SELECT id FROM {t} WHERE status IS NULL ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED)
RETURNING id, refl_name, length_km """

def _log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(msg, "OTDR", level)
    if iface:
        iface.messageBar().pushMessage("OTDR", msg, level, 10)

def _norm(s):
    return (s or "").strip().lower()

def _km(value):
    return float(str(value).replace(",", ".").strip())


def _q(s):
    return "NULL" if not s else "'" + str(s).replace("'", "''") + "'"


def _line_layers():
    return [
        l for l in QgsProject.instance().mapLayers().values()
        if isinstance(l, QgsVectorLayer) and l.geometryType() == QgsWkbTypes.LineGeometry
    ]


def _features(layer, expr=None):
    req = QgsFeatureRequest()
    if expr:
        req.setFilterExpression(expr)
    ordered = bool(ORDER_FIELD) and layer.fields().indexOf(ORDER_FIELD) >= 0
    if ordered:
        req.addOrderBy(QgsExpression.quotedColumnRef(ORDER_FIELD))
    feats = [f for f in layer.getFeatures(req) if f.hasGeometry()]
    if not ordered:
        feats.sort(key=lambda f: f.id())
    return feats


def find_route(refl_name):
    """Возвращает (слой, [объекты]) трассы по названию опорной рефлектограммы."""
    key = _norm(refl_name)
    if not key:
        raise ValueError("Пустое название рефлектограммы")
    layers = _line_layers()
    for l in layers:
        if key in (_norm(l.name()), _norm(QgsDataSourceUri(l.source()).table())):
            feats = _features(l)
            if feats:
                return l, feats
    if REFL_FIELD:
        expr = "lower(trim({})) = {}".format(
            QgsExpression.quotedColumnRef(REFL_FIELD), QgsExpression.quotedValue(key))
        for l in layers:
            if l.fields().indexOf(REFL_FIELD) < 0:
                continue
            feats = _features(l, expr)
            if feats:
                return l, feats
    raise LookupError(f"Трасса для рефлектограммы {refl_name!r} не найдена")


def _distance_area(crs):
    prj = QgsProject.instance()
    da = QgsDistanceArea()
    da.setSourceCrs(crs, prj.transformContext())
    ell = prj.ellipsoid()
    da.setEllipsoid(ell if ell and ell != "NONE" else DEFAULT_ELLIPSOID)
    return da


def _parts(feats):
    out = []
    for f in feats:
        g = QgsGeometry(f.geometry())
        g.convertToStraightSegment()
        for p in g.parts():
            pts = [QgsPointXY(v) for v in p.vertices()]
            if len(pts) >= 2:
                out.append(pts)
    return out


def _chain(parts, da):
    """Цепочка от первой вершины первой полилинии; возвращает (вершины, непристыкованные)."""
    route = list(parts[0])
    rest = [list(p) for p in parts[1:]]
    while rest:
        end = route[-1]
        best = None
        for i, p in enumerate(rest):
            for rev, q in ((False, p[0]), (True, p[-1])):
                d = da.measureLine(end, q)
                if best is None or d < best[0]:
                    best = (d, i, rev)
        d, i, rev = best
        if d > SNAP_TOL_M:
            break
        p = rest.pop(i)
        if rev:
            p.reverse()
        route.extend(p[1:] if d == 0 else p)
    return route, rest


def _walk(route, da, target_m):
    """Суммирует отрезки до target_m; возвращает (точка, пройдено_м)."""
    acc = 0.0
    for a, b in zip(route, route[1:]):
        seg = da.measureLine(a, b)
        if seg > 0 and acc + seg >= target_m:
            t = (target_m - acc) / seg
            return QgsPointXY(a.x() + t * (b.x() - a.x()), a.y() + t * (b.y() - a.y())), target_m
        acc += seg
    return route[-1], acc


def compute(refl_name, length_km):
    """Возвращает (слой трассы, точка в СК слоя, вершины трассы, пройдено_м, примечание)."""
    km = _km(length_km)
    layer, feats = find_route(refl_name)
    da = _distance_area(layer.crs())
    parts = _parts(feats)
    if not parts:
        raise ValueError(f"В слое {layer.name()!r} нет линейной геометрии")
    route, rest = _chain(parts, da)
    target = max(0.0, (km * 1000.0 - START_OFFSET_M) / CABLE_FACTOR)
    pt, done = _walk(route, da, target)

    notes = []
    if target - done > 0:
        notes.append(f"длина больше трассы на {target - done:.1f} м, метка в конце")
    if rest:
        notes.append(f"не пристыковано участков: {len(rest)}")
    return layer, pt, route, done, "; ".join(notes)

#symbol = QgsMarkerSymbol.createSimple(['name':'arrow'])
symbol = QgsMarkerSymbol.createSimple({'name':'x','color': '255,0,0,255,rgb:1,0,0,1','size':'6','outline_width': '2.5','outline_width_unit': 'MM' })
def _style(vl):
    #sym = vl.renderer().symbol()
    vl.renderer().setSymbol(symbol)
    #sym.setColor(QColor(220, 0, 0))
    #sym.setSize(6)
    lbl = QgsPalLayerSettings()
    lbl.fieldName = r""""refl_name" || '\n' || format_number("length_km", 4) || ' км'"""
    lbl.isExpression = True
    vl.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
    vl.setLabelsEnabled(True)


def _show(pt, route, crs):
    if not iface:
        return
    canvas = iface.mapCanvas()
    xf = QgsCoordinateTransform(crs, canvas.mapSettings().destinationCrs(), QgsProject.instance())
    canvas.setCenter(xf.transform(pt))
    canvas.refresh()
    canvas.flashGeometries([QgsGeometry.fromPolylineXY(route), QgsGeometry.fromPointXY(pt)], crs)


def _report(refl_name, km, done, layer, note):
    _log(f"{refl_name}: {km:.3f} км -> {done:.1f} м по трассе, слой {layer.name()!r}"
         + (f" ({note})" if note else ""),
         Qgis.Warning if note else Qgis.Info)


# --- ручной режим (без БД) ---------------------------------------------------

def _mark_layer(crs):
    found = QgsProject.instance().mapLayersByName(MARK_LAYER)
    if found:
        return found[0]
    vl = QgsVectorLayer(f"Point?crs={crs.authid()}", MARK_LAYER, "memory")
    vl.setCrs(crs)
    vl.dataProvider().addAttributes([
        QgsField("refl_name", _STR), QgsField("length_km", _DBL), QgsField("route_m", _DBL),
        QgsField("ts", _STR), QgsField("note", _STR),
    ])
    vl.updateFields()
    _style(vl)
    QgsProject.instance().addMapLayer(vl)
    return vl


def _add_mark(pt, crs, attrs):
    vl = _mark_layer(crs)
    xf = QgsCoordinateTransform(crs, vl.crs(), QgsProject.instance())
    f = QgsFeature(vl.fields())
    f.setGeometry(QgsGeometry.fromPointXY(xf.transform(pt)))
    for k, v in attrs.items():
        i = vl.fields().indexOf(k)
        if i >= 0:
            f.setAttribute(i, v)
    ok, _ = vl.dataProvider().addFeatures([f])
    if not ok:
        raise RuntimeError(f"Не удалось записать метку в слой {vl.name()!r}")
    vl.updateExtents()
    vl.triggerRepaint()


def locate(refl_name, length_km):
    """Ставит метку на трассе рефлектограммы refl_name на расстоянии length_km от начала."""
    km = _km(length_km)
    layer, pt, route, done, note = compute(refl_name, km)
    _add_mark(pt, layer.crs(), {
        "refl_name": refl_name, "length_km": km, "route_m": round(done, 2),
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "note": note,
    })
    _show(pt, route, layer.crs())
    _report(refl_name, km, done, layer, note)
    return pt


# --- очередь событий в PostgreSQL --------------------------------------------

def _pg():
    md = QgsProviderRegistry.instance().providerMetadata("postgres")
    if PG_CONNECTION:
        conn = md.findConnection(PG_CONNECTION)
        if conn is None:
            raise LookupError(f"Нет подключения PostgreSQL {PG_CONNECTION!r}")
        return conn
    for l in QgsProject.instance().mapLayers().values():
        if l.providerType() == "postgres":
            return md.createConnection(QgsDataSourceUri(l.source()).connectionInfo(False), {})
    raise LookupError("В проекте нет PostGIS-слоёв: задайте PG_CONNECTION")


def _events_layer(conn):
    schema, table = EVENTS_TABLE.split(".")
    for l in QgsProject.instance().mapLayers().values():
        if l.providerType() == "postgres":
            u = QgsDataSourceUri(l.source())
            if (u.schema(), u.table()) == (schema, table):
                return l
    u = QgsDataSourceUri(conn.uri())
    u.setDataSource(schema, table, "geom", "", "id")
    vl = QgsVectorLayer(u.uri(False), EVENTS_LAYER, "postgres")
    if not vl.isValid():
        raise RuntimeError(f"Не удалось открыть {EVENTS_TABLE}")
    _style(vl)
    QgsProject.instance().addMapLayer(vl)
    return vl


def poll():
    """Обрабатывает новые строки EVENTS_TABLE."""
    conn = _pg()
    rows = sorted(conn.executeSql(_CLAIM.format(t=EVENTS_TABLE)), key=lambda r: int(r[0]))
    if not rows:
        return
    dst = QgsCoordinateReferenceSystem(f"EPSG:{EVENTS_SRID}")
    last = None
    for eid, name, km in rows:
        eid = int(eid)
        try:
            layer, pt, route, done, note = compute(name, km)
            p = QgsCoordinateTransform(layer.crs(), dst, QgsProject.instance()).transform(pt)
            conn.executeSql(
                f"UPDATE {EVENTS_TABLE} SET status = 'ok', processed_at = now(), "
                f"route_m = {done:.2f}, note = {_q(note)}, "
                f"geom = ST_SetSRID(ST_MakePoint({p.x():.3f}, {p.y():.3f}), {EVENTS_SRID}) "
                f"WHERE id = {eid}")
            _report(name, _km(km), done, layer, note)
            last = (pt, route, layer.crs())
        except Exception as e:
            conn.executeSql(
                f"UPDATE {EVENTS_TABLE} SET status = 'error', processed_at = now(), "
                f"note = {_q(e)} WHERE id = {eid}")
            _log(f"{name}: {e}", Qgis.Critical)
    vl = _events_layer(conn)
    vl.reload()
    vl.triggerRepaint()
    if last:
        _show(*last)


def _safe_poll():
    try:
        poll()
    except Exception as e:
        QgsMessageLog.logMessage(f"Опрос {EVENTS_TABLE}: {e}", "OTDR", Qgis.Critical)


def stop():
    t = iface.mainWindow().findChild(QTimer, _TIMER)
    if t:
        t.stop()
        t.setObjectName("")
        t.deleteLater()


def start(interval_s=POLL_SEC):
    stop()
    t = QTimer(iface.mainWindow())
    t.setObjectName(_TIMER)
    t.timeout.connect(_safe_poll)
    t.start(int(interval_s * 1000))
    _safe_poll()


if iface:
    start()
```

Скрипт "snmp_trap_receiver_frust.py":

```python
import os
import re
import sys

import psycopg
from psycopg.types.json import Jsonb
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.rfc1902 import OctetString
from pysnmp.smi import builder, view, compiler

# --- Передача событий в PostgreSQL (таблица otdr.events, sql/otdr_events.sql) ---
# Строка подключения libpq; пароль - через PGPASSWORD или pgpass.conf.
PG_DSN = os.environ.get("PG_DSN", "postgresql://otdr_snmp:***@localhost:5432/sasplanet_marks")

# Поиск в тексте любого varbind-а (OID не важен), пример:
# "... Опорная рефлектограмма:fru.sor ... место: 1,000 км. ..."
REFL_RE = re.compile(r"рефлектограмма\s*:\s*(\S+?)\.sor\b", re.IGNORECASE)
LEN_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*км\b", re.IGNORECASE)

_pg = None


def _extract(texts):
    """(имя рефлектограммы, длина в км) из первых совпадений по всем varbind-ам."""
    refl = length_km = None
    for text in texts:
        if refl is None:
            m = REFL_RE.search(text)
            if m:
                refl = m.group(1)
        if length_km is None:
            m = LEN_RE.search(text)
            if m:
                length_km = float(m.group(1).replace(",", "."))
    return refl, length_km


def save_event(src_ip, refl_name, length_km, raw):
    """INSERT события в otdr.events; одна попытка переподключения."""
    global _pg
    err = None
    for _ in range(2):
        try:
            if _pg is None or _pg.closed:
                _pg = psycopg.connect(PG_DSN, autocommit=True)
            _pg.execute(
                "INSERT INTO otdr.events (src_ip, refl_name, length_km, raw) "
                "VALUES (%s::inet, %s, %s, %s)",
                (src_ip, refl_name, length_km, Jsonb(raw)),
            )
            print(f"-> otdr.events: {refl_name!r}, {length_km} км")
            return True
        except psycopg.OperationalError as e:
            err, _pg = e, None
        except psycopg.Error as e:
            err = e
            break
    print(f"Не удалось записать событие в БД: {err}")
    return False


def main():
    """
    SNMP Trap receiver that:
    - listens on UDP/162
    - loads local MIB `SVP-GAMMA-MIB` from the same directory as this script
    - prints trap contents in human-readable form
    - writes (reference reflectogram name, length km) to PostgreSQL otdr.events

    Требования:
        pip install "pysnmp==4.4.12" "pysmi<1" "pyasn1<0.5" "psycopg[binary]"
        (Python 3.12+: дополнительно pyasyncore; pysnmp 5+ и pyasn1 0.5+ с этим кодом несовместимы)"""

    # Настройки
    LISTEN_IP = "0.0.0.0"
    LISTEN_PORT = 10162       # стандартный SNMP trap порт
    # Имя MIB-модуля (из первой строки файла: SVP-GAMMA-MIB DEFINITIONS ::= BEGIN)
    MIB_MODULE_NAME = "SVP-GAMMA-MIB"

    # Путь к каталогу, где лежит MIB-файл
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mib_dir = script_dir  # ваш файл SVP-GAMMA-MIB_rev2.txt лежит на рабочем столе рядом со скриптом

    # Создаём SNMP-движок
    snmpEngine = engine.SnmpEngine()

    # Настраиваем транспорт: UDP слушает порт 162 на всех интерфейсах
    try:
        config.addTransport(
            snmpEngine,
            udp.domainName,
            udp.UdpTransport().openServerMode((LISTEN_IP, LISTEN_PORT)),
        )
    except Exception as e:
        print(f"Не удалось открыть UDP порт {LISTEN_PORT}: {e}")
        print("Попробуйте:")
        print("- запустить скрипт от имени администратора; или")
        print("- изменить LISTEN_PORT в коде (например, на 10162) и перезапустить.")
        sys.exit(1)

    # Настраиваем SNMPv1/v2c сообщество (community). Подстройте под ваш агент при необходимости.
    # Если у вас другое community, поменяйте 'public' на нужное.
    config.addV1System(snmpEngine, "my-area", "public")

    # Разрешаем приём trap-ов от всех источников
    config.addTargetParams(snmpEngine, "my-params", "my-area", "noAuthNoPriv", 1)

    # --- Настройка MIB ---

    mibBuilder = snmpEngine.getMibBuilder()

    # Добавляем локный каталог с текстовыми MIB-файлами
    mibBuilder.addMibSources(builder.DirMibSource(mib_dir))

    # Добавляем компилятор pysmi, чтобы из текстового MIB сделать внутреннее представление для pysnmp
    compiler.addMibCompiler(mibBuilder, sources=[f"file://{mib_dir}"])

    # Пытаемся загрузить ваш MIB
    try:
        mibBuilder.loadModules(MIB_MODULE_NAME)
    except Exception as e:
        print("Ошибка при загрузке MIB модуля.")
        print(f"Ожидается, что текстовый файл MIB лежит здесь: {mib_dir}")
        print(f"Имя модуля: {MIB_MODULE_NAME}")
        print(f"Детали: {e}")
        print("Убедитесь, что файл 'SVP-GAMMA-MIB_rev2.txt' действительно находится рядом со скриптом.")
        # Не выходим полностью: даже без MIB-а можно печатать числовые OID-ы

    mibViewController = view.MibViewController(mibBuilder)

    # --- Callback для приёма trap-ов ---

    def cb_fun(snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
        # Определяем IP и порт источника trap-а
        transportDomain, transportAddress = snmpEngine.msgAndPduDsp.getTransportInfo(stateReference)
        src_ip, src_port = transportAddress

        print("=" * 80)
        print(f"Получен SNMP trap от {src_ip}:{src_port}")
        texts = []  # значения всех varbind-ов текстом
        raw_map = {}

        # Перебираем все пары OID = значение
        for name, val in varBinds:
            # Пытаемся перевести числовой OID в символическое имя по MIB
            try:
                oid, label, suffix = mibViewController.getNodeName(name)
                modName, symName, _ = mibViewController.getNodeLocation(oid)

                # Строим "хвост" OID-а, если он есть (индексы и т.п.)
                if suffix:
                    index_str = "." + ".".join(str(x) for x in suffix)
                else:
                    index_str = ""

                oid_str = f"{modName}::{symName}{index_str}"
            except Exception:
                # Если не удалось сопоставить с MIB, печатаем как числовой OID
                oid_str = f"{name.prettyPrint()}"

            # Преобразуем значение в человекочитаемый вид
            value_str = val.prettyPrint()
            plain = value_str
            if isinstance(val, OctetString):
                raw = bytes(val)
                # Пытаемся декодировать как cp1251 (Windows-1251), т.к. у вас русский текст
                try:
                    text = raw.decode("cp1251")
                    plain = text
                    value_str = f"{text} (hex: {raw.hex()})"
                except UnicodeDecodeError:
                    # Если не получилось, оставляем hex
                    value_str = f"0x{raw.hex()}"

            print(f"{oid_str} = {value_str}")
            texts.append(plain)
            raw_map[oid_str] = plain

        # Извлекаем название опорной рефлектограммы и длину, передаём в БД
        refl, length_km = _extract(texts)
        if refl and length_km is not None:
            try:
                save_event(src_ip, refl, length_km, raw_map)
            except Exception as e:
                print(f"Ошибка записи в БД: {e!r}")
        else:
            print("В trap-е не найдены рефлектограмма (*.sor) и/или длина (км): в БД не записан")

        print("=" * 80)
        print()

    # Регистрируем обработчик уведомлений
    ntfrcv.NotificationReceiver(snmpEngine, cb_fun)

    print(f"SNMP Trap приёмник запущен на {LISTEN_IP}:{LISTEN_PORT}")
    print("Для остановки нажмите Ctrl+C.")

    # Запускаем основной цикл обработки
    try:
        from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher  # noqa: F401
        # Используется внутри snmpEngine.transportDispatcher
        snmpEngine.transportDispatcher.jobStarted(1)  # чтобы цикл не завершался сразу
        snmpEngine.transportDispatcher.runDispatcher()
    except KeyboardInterrupt:
        print("\nОстановка по Ctrl+C")
    finally:
        snmpEngine.transportDispatcher.closeDispatcher()
        if _pg is not None:
            _pg.close()


if __name__ == "__main__":
    main()
```

## 1. Ассистент

Плагин готов и запушен в ветку `claude/qgis-snmp-trap-plugin-9t4s6k`, каталог `otdr_marks/`. Проверен на QGIS Server 3.34 с PostgreSQL 16 и PostGIS 3.4 под spawn-fcgi (3 процесса): события обрабатываются без входящих запросов, метки с подписями видны в WMS GetMap, макеты проекта при сохранении не теряются. QGIS 4 не запускал: используемые вызовы сверил с его исходниками.

**Как работает**
- Опрос `otdr.events` ведёт один процесс QGIS Server в фоновом потоке, раз в 5 с. QTimer не годится: процесс FastCGI между запросами не обрабатывает события Qt.
- Берутся строки с пустым `status` (с флагом `FOR UPDATE SKIP LOCKED`). Для каждой ищется линейный слой проекта, у которого имя (или имя таблицы) совпадает с `refl_name` без учёта регистра.
- От начала трассы откладывается расстояние, в таблицу пишутся `status`, `processed_at`, `route_m`, `note`, `geom` (EPSG:3395). Расстояние меряется по эллипсоиду. Участки трассы сшиваются, кривые переводятся в отрезки.
- Метки рисует слой «OTDR события» (PostGIS `otdr.events`): красный крест, повёрнутый на 45°, и подпись `'Обрыв!Время:' || format_date("received_at", 'yyyy/MM/dd/HH:mm:ss')`. Если слоя в проекте нет, плагин добавляет его и сохраняет проект в `public.qgis_projects` при запуске.
- Настройки (`POLL_SEC`, `EVENTS_SRID`, `LABEL_EXPR`, `CABLE_FACTOR`, `START_OFFSET_M`, `SNAP_TOL_M`) — в начале `otdr_marks/otdr_marks.py`.

**Установка**
```bash
git clone -b claude/qgis-snmp-trap-plugin-9t4s6k https://github.com/Ultramiloserdie/ultravossoedinenie /tmp/uv
sudo mkdir -p /opt/qgis-server/plugins
sudo cp -r /tmp/uv/otdr_marks /opt/qgis-server/plugins/
```

Переменные окружения процесса QGIS Server.

Apache с mod_fcgid — в `<VirtualHost>` QGIS Server:
```apache
FcgidInitialEnv QGIS_PLUGINPATH "/opt/qgis-server/plugins"
FcgidInitialEnv OTDR_PG_SERVICE "<сервис из pg_service.conf>"
FcgidInitialEnv OTDR_PROJECT "<имя проекта в public.qgis_projects>"
```
```bash
sudo systemctl restart apache2
```

nginx со spawn-fcgi (systemd):
```bash
sudo systemctl edit <unit QGIS Server>
```
```ini
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=<сервис>
Environment=OTDR_PROJECT=<проект>
```
```bash
sudo systemctl restart <unit QGIS Server>
```

`OTDR_PROJECT` можно не задавать, если в `public.qgis_projects` один проект.

**Один раз после первого запуска**
1. Ещё раз перезапустить QGIS Server, чтобы все процессы перечитали проект с новым слоем.
2. Перегенерировать конфигурацию QWC: в qwc-admin-gui → Generate service configuration, либо `curl -X POST "http://localhost:5010/generate_configs?tenant=default"` (это адрес qwc-config-generator в qwc-docker). Если `permissions_default_allow=false`, выдать права на слой «OTDR события».

**Важно**
- **`route_m` при вставке пустой:** SNMP-скрипт его не пишет. Поэтому расстояние берётся из `length_km`, умножается на 1000 и записывается в `route_m`. Если `route_m` заполнен заранее, используется он.
- **`stasus` или `status`:** в описании таблицы колонка названа `stasus`, в референсе — `status`. Плагин находит любую из двух.
- **Цвет креста в референсе:** символ `x` с одним параметром `color` рисуется цветом обводки (по умолчанию тёмно-серым), а не красным. В плагине задан `outline_color`.
- **Обновление в QWC2:** сам QWC2 карту не обновляет. Метка появится при следующей перерисовке карты.
- **Перезапись проекта:** проект сохраняет QGIS Server, один раз. Его версия должна быть не ниже версии QGIS Desktop, иначе пропадут свойства, которых сервер не знает.
- **Слой в Desktop:** слой использует `service=<OTDR_PG_SERVICE>`. На ПК с QGIS Desktop в `pg_service.conf` нужен сервис с тем же именем.
- **Готовый слой otdr.events:** если такой слой уже есть в проекте (например, добавленный референс-скриптом), плагин не создаёт второй, а переоформляет имеющийся.
- **Референс-скрипт:** не запускать его в Desktop параллельно — событие обработает тот, кто заберёт его первым.
- **Старт при mod_fcgid:** процессы QGIS Server стартуют по первому запросу. Опрос начнётся после первого обращения к серверу.
- **Журнал:** записи с тегом `OTDR` попадают в лог QGIS Server, только когда процесс, ведущий опрос, обрабатывает запрос. Сразу результат каждого события видно в `otdr.events.status` и `note`.

---

## 2. Пользователь

> nginx со spawn-fcgi (systemd):

Объясни вот этот блок подробнее

## 2. Ассистент

При связке с nginx процесс `qgis_mapserv.fcgi` запускает systemd: unit поднимает `spawn-fcgi`, тот запускает QGIS Server. nginx только пересылает запросы в его unix-сокет (`fastcgi_pass`). Этот блок добавляет переменные окружения в тот unit.

**Почему в unit, а не в nginx**
- `QGIS_PLUGINPATH` QGIS Server читает один раз, при старте процесса, когда загружает плагины. Плагин читает `OTDR_*` в тот же момент. Всё это происходит до первого запроса.
- `fastcgi_param` в nginx передаёт параметры отдельного запроса. При старте процесса их ещё нет, поэтому переменные задаются только через `Environment=` (или `EnvironmentFile=`) в unit.

**1. Найти unit**
```bash
systemctl list-unit-files | grep -iE 'qgis|fcgi'
systemctl cat qgis-server.service
```
В документации QGIS два варианта:
- `qgis-server.service` с `ExecStart=spawn-fcgi -s /var/run/qgisserver.socket ... -n /usr/lib/cgi-bin/qgis_mapserv.fcgi`. Ключ `-n` означает «без fork», то есть процесс один.
- Шаблон `qgis-server@.service` вместе с `qgis-server@.socket`: по процессу на экземпляр (`@1`, `@2`…). Переменные задаются в шаблоне и действуют на все экземпляры.

Вариант с `fcgiwrap` не подходит: QGIS там работает как CGI, процесс живёт один запрос, фонового опроса не будет.

**2. Добавить переменные отдельным файлом (drop-in)**
```bash
sudo systemctl edit qgis-server.service        # для шаблона: sudo systemctl edit qgis-server@.service
```
Откроется редактор файла `/etc/systemd/system/qgis-server.service.d/override.conf`, в него вписать:
```ini
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=<сервис из pg_service.conf>
Environment="OTDR_PROJECT=<имя проекта>"
```
- Заголовок `[Service]` обязателен, без него systemd проигнорирует строки.
- Если в значении есть пробелы (например, в имени проекта), всё `KEY=value` берётся в кавычки.
- Drop-in не меняет исходный unit и переживает обновление пакетов. `systemctl edit` сам выполняет `daemon-reload`.
- Если в unit уже есть `EnvironmentFile=/etc/qgis-server/env`, можно дописать те же строки (`KEY=value`) туда.

**3. Перезапуск**
```bash
sudo systemctl restart qgis-server.service     # для шаблона: sudo systemctl restart 'qgis-server@*.service'
```
Сокеты экземпляров перезапускать не нужно. Конфиг nginx для плагина менять не нужно. `fastcgi_pass` должен указывать на тот же сокет, что `-s` у spawn-fcgi или `ListenStream=` у сокета.

**pg_service.conf — особенность FastCGI**
QGIS Server принимает запросы через `FCGI_Accept` из libfcgi. На время каждого запроса эта функция подменяет окружение процесса параметрами запроса. Поэтому `PGSERVICEFILE` из `Environment=` libpq видит только до первого запроса.
- Самое простое — положить файл туда, где libpq найдёт его без переменных: `/etc/postgresql-common/pg_service.conf` (стандартное место в Ubuntu) или `~/.pg_service.conf` пользователя процесса. Права:
  ```bash
  sudo chown root:www-data /etc/postgresql-common/pg_service.conf && sudo chmod 640 /etc/postgresql-common/pg_service.conf
  ```
- Если файл лежит в другом месте, нужны обе настройки:
  - `Environment=PGSERVICEFILE=/путь` в unit — для старта процесса и фонового опроса;
  - `fastcgi_param PGSERVICEFILE /путь;` в `location` nginx — для подключений QGIS Server во время запросов.

Эта же подмена ломала опрос в плагине. После первого запроса фоновый поток терял переменные процесса и читал освобождённую память. На стенде с нестандартным `PGSERVICEFILE` новое событие получало `status = 'error'`.

Исправил в коммите `4e5228f`, ветка та же: после каждого ответа плагин возвращает окружение процесса. Проверка на стенде: 240 параллельных GetMap и 120 событий обработаны, процессы QGIS Server не упали. Чтобы обновить плагин:
```bash
cd /tmp/uv && git pull && sudo cp -r otdr_marks /opt/qgis-server/plugins/ && sudo systemctl restart qgis-server.service
```

---

## 3. Пользователь

```
ser@server:~$ systemctl list-unit-files | grep -iE 'qgis|fcgi'
qgis-server@.service                         indirect        enabled
qgis-server@.socket                          indirect        enabled
ser@server:~$ systemctl cat qgis-server.service
No files found for qgis-server.service.
```

## 3. Ассистент

У вас не spawn-fcgi, а второй вариант: шаблон `qgis-server@.service` + `qgis-server@.socket`. Сокет держит systemd и сам передаёт его процессу. Отдельного `qgis-server.service` нет, поэтому `systemctl cat` ничего не нашёл. Переменные задаются в шаблоне и действуют на все экземпляры.

**1. Посмотреть шаблон и экземпляры**
```bash
systemctl cat qgis-server@.service
systemctl list-units --all 'qgis-server@*'
```
В выводе `cat` найдите строку `User=`: под этим пользователем работает QGIS Server (обычно `www-data`). Второй командой увидите номера экземпляров (`@1`, `@2`…).

**2. Добавить переменные в шаблон**
```bash
sudo systemctl edit qgis-server@.service
```
Вписать в редактор:
```ini
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=<сервис из pg_service.conf>
Environment="OTDR_PROJECT=<имя проекта>"
```
Файл сохранится как `/etc/systemd/system/qgis-server@.service.d/override.conf`.

**3. Перезапустить экземпляры**
```bash
sudo systemctl restart 'qgis-server@*.service'
```
Сокеты (`qgis-server@N.socket`) перезапускать не нужно.

**4. Автозапуск после перезагрузки**
```bash
systemctl is-enabled qgis-server@1.service
```
- Если ответ `enabled`, экземпляр стартует при загрузке и опрос идёт сразу.
- Если нет, процесс поднимется только при первом запросе к сокету, и до этого опроса не будет. Включить автозапуск:
  ```bash
  sudo systemctl enable qgis-server@1.service
  ```
  Плагину достаточно одного запущенного процесса — опрос ведёт только один.

**5. Где положить pg_service.conf**
Без переменной `PGSERVICEFILE` libpq ищет файл в двух местах:
- `/etc/postgresql-common/pg_service.conf`;
- `~/.pg_service.conf` пользователя из `User=`. Для `www-data` это `/var/www/.pg_service.conf`.

Права для системного файла:
```bash
sudo chown root:www-data /etc/postgresql-common/pg_service.conf
sudo chmod 640 /etc/postgresql-common/pg_service.conf
```

---

## 4. Пользователь

Что значит: "Environment=OTDR_PG_SERVICE=<сервис из pg_service.conf>"

## 4. Ассистент

Это имя секции в квадратных скобках из `pg_service.conf`. По нему плагин подключается к БД `sasplanet_marks`.

Пример `pg_service.conf`:
```ini
[sasplanet]
host=localhost
port=5432
dbname=sasplanet_marks
user=postgres
password=...
```
Здесь сервис называется `sasplanet`, значит строка в unit будет такой:
```ini
Environment=OTDR_PG_SERVICE=sasplanet
```

Плагин берёт это имя для трёх вещей:
- подключение к `otdr.events` для опроса и записи меток;
- чтение и сохранение проекта в `public.qgis_projects`;
- источник данных слоя «OTDR события» в проекте.

Посмотреть имена сервисов в файле:
```bash
grep '^\[' /etc/postgresql-common/pg_service.conf
```

Проще всего взять тот же сервис, через который QGIS Server уже открывает проект: он стоит после `service=` в параметре `MAP`, например `MAP=postgresql:?service=sasplanet&schema=public&project=...`.

---

## 5. Пользователь

> Где положить pg_service.conf
> Без переменной PGSERVICEFILE libpq ищет файл в двух местах:
>
> /etc/postgresql-common/pg_service.conf;
> ~/.pg_service.conf пользователя из User=. Для www-data это /var/www/.pg_service.conf.

pg_service.conf лежит в общей папке Windows (сетевая папка)

## 5. Ассистент

Сервер Ubuntu не читает этот файл из Windows-папки: libpq ищет его только в локальной файловой системе. Нужна локальная копия на сервере.

**Вариант 1 (рекомендую): скопировать на сервер**
```bash
sudo apt install smbclient
smbclient //<windows-хост>/<общая_папка> -U <пользователь_windows> -c 'get pg_service.conf /tmp/pg_service.conf'
sudo install -o root -g www-data -m 640 /tmp/pg_service.conf /etc/postgresql-common/pg_service.conf
rm /tmp/pg_service.conf
sudo systemctl restart 'qgis-server@*.service'
```
Если `smbclient` ставить не хотите, можно создать `/etc/postgresql-common/pg_service.conf` вручную с тем же содержимым.

В скопированном файле проверьте `host=`. Если там указано имя Windows-машины, которое сервер не разрешает, или адрес, недоступный с сервера, замените на `localhost` или IP сервера PostgreSQL.

Минус: при смене пароля или параметров файл нужно обновлять в двух местах — на Windows-ресурсе и на сервере.

**Вариант 2: подключить папку и указать путь к файлу**
1. Смонтировать папку постоянно (пакет `cifs-utils`, запись в `/etc/fstab`).
2. Указать путь к файлу и в systemd, и в nginx, иначе из-за FastCGI часть подключений файла не найдёт:
   - в `sudo systemctl edit qgis-server@.service`: `Environment=PGSERVICEFILE=/mnt/<папка>/pg_service.conf`;
   - в `location` nginx для QGIS: `fastcgi_param PGSERVICEFILE /mnt/<папка>/pg_service.conf;`.

Минусы:
- при недоступности Windows-машины или сети QGIS Server и плагин не подключатся к БД;
- при загрузке сервера папка может смонтироваться позже, чем стартует QGIS Server;
- пароль от БД передаётся по сети.

Как QGIS Server открывает проект сейчас, если файл есть только на Windows-ресурсе?

---

## 6. Пользователь

> /etc/postgresql-common/pg_service.conf вручную с тем же содержимым.

Дай гайд, как скопировать папку в ручную

## 6. Ассистент

Копировать нужно один файл `pg_service.conf`, не всю папку.

**1. На Windows**
Откройте `\\<хост>\<общая_папка>\pg_service.conf` в Блокноте, выделите всё (Ctrl+A) и скопируйте (Ctrl+C).

**2. На сервере (через SSH, например в PuTTY или Windows Terminal)**
```bash
sudo nano /etc/postgresql-common/pg_service.conf
```
- Вставьте текст правой кнопкой мыши (в PuTTY) или Ctrl+Shift+V (в Windows Terminal).
- Сохраните: Ctrl+O, затем Enter. Выйдите: Ctrl+X.

Если файл уже существовал, дополните его новыми секциями, а не затирайте.

**3. Проверьте `host=`**
Указанный там адрес PostgreSQL должен быть доступен с сервера. Если PostgreSQL стоит на этом же сервере, ставьте `localhost`. Посмотреть, что получилось:
```bash
sudo grep -nE '^\[|host=' /etc/postgresql-common/pg_service.conf
```

**4. Права: файл читают только root и www-data, потому что в нём пароль**
```bash
sudo chown root:www-data /etc/postgresql-common/pg_service.conf
sudo chmod 640 /etc/postgresql-common/pg_service.conf
```

**5. Перезапуск QGIS Server**
```bash
sudo systemctl restart 'qgis-server@*.service'
```

После этого в `Environment=OTDR_PG_SERVICE=` укажите имя секции из квадратных скобок этого файла.

---

## 7. Пользователь

> Вписать в редактор:
>
> Файл сохранится как /etc/systemd/system/qgis-server@.service.d/override.conf

Как проверить внесено ли изменение

## 7. Ассистент

Проверка в три шага: файл, unit, запущенный процесс. В командах используется экземпляр `@1`; номер возьмите из `systemctl list-units --all 'qgis-server@*'`.

**1. Файл создан**
```bash
cat /etc/systemd/system/qgis-server@.service.d/override.conf
```
Должны быть строка `[Service]` и ваши строки `Environment=`.

**2. systemd подхватил файл**
```bash
systemctl cat qgis-server@1.service
```
В конце вывода должен быть блок `# /etc/systemd/system/qgis-server@.service.d/override.conf` с вашими строками.

```bash
systemctl show qgis-server@1.service -p Environment
```
В строке `Environment=` должны быть `QGIS_PLUGINPATH=...`, `OTDR_PG_SERVICE=...` и `OTDR_PROJECT=...`.

Если их нет:
```bash
sudo systemctl daemon-reload
```

**3. Работающий процесс получил переменные**
Это покажет, был ли перезапуск после правки.
```bash
PID=$(systemctl show -p MainPID --value qgis-server@1.service)
sudo tr '\0' '\n' < /proc/$PID/environ | grep -E 'QGIS_PLUGINPATH|OTDR_'
```
- `MainPID=0`: процесс не запущен. Запустить:
  ```bash
  sudo systemctl start qgis-server@1.service
  ```
- Пусто при запущенном процессе: он стартовал до правки. Перезапустить:
  ```bash
  sudo systemctl restart 'qgis-server@*.service'
  ```

---

## 8. Пользователь

Это ([Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=<сервис из pg_service.conf>
Environment="OTDR_PROJECT=<имя проекта>") вписать в виде "# Enviroment..." или просто под сервисом

## 8. Ассистент

Без `#`. Строка, начинающаяся с `#`, — это комментарий, systemd её игнорирует.

В Ubuntu 24.04 `sudo systemctl edit qgis-server@.service` открывает редактор с подсказкой такого вида:
```
### Editing /etc/systemd/system/qgis-server@.service.d/override.conf
### Anything between here and the comment below will become the contents of the drop-in file

<-- сюда

### Edits below this comment will be discarded
...
```
Текст нужно вписать между этими двумя строками `###`, без `#` и угловых скобок, подставив свои значения:
```ini
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=sasplanet
Environment="OTDR_PROJECT=Проект ОТДР"
```
- `sasplanet` замените на имя секции из квадратных скобок в `pg_service.conf`.
- `Проект ОТДР` замените на имя вашего проекта. Кавычки вокруг всей строки нужны только если в имени есть пробелы.
- Если в `public.qgis_projects` один проект, строку `OTDR_PROJECT` можно не писать.

Всё, что ниже строки «Edits below this comment will be discarded», — закомментированная копия исходного unit. Её не трогать: изменения там не сохранятся.

Сохранить и выйти (nano): Ctrl+O, Enter, Ctrl+X. Затем перезапустить:
```bash
sudo systemctl restart 'qgis-server@*.service'
```

---

## 9. Пользователь

Я вписываю в таком виде, а файл не сохраняется:

```
### Editing /etc/systemd/system/qgis-server@.service.d/override.conf
### Anything between here and the comment below will become the contents of the drop-in file
[Service]
Environment=QGIS_PLUGINPATH=/opt/qgis-server/plugins
Environment=OTDR_PG_SERVICE=gisdb
Environment="OTDR_PROJECT=q2s"
### Edits below this comment will be discarded


### /etc/systemd/system/qgis-server@.service
# [Unit]
# Description=QGIS Server Service (instance %i)
#
# [Service]
# User=www-data
# Group=www-data
# StandardInput=socket
# StandardOutput=null
# StandardError=journal
# EnvironmentFile=/etc/qgis-server/env
# ExecStart=/usr/lib/cgi-bin/qgis_mapserv.fcgi
# Restart=always
#
# [Install]
# WantedBy=multi-user.target
```

## 9. Ассистент

Содержимое вписано правильно. Значит, дело в том, как сохраняется файл.

**Как работает сохранение в `systemctl edit`**
1. Команда запускается с `sudo`: `sudo systemctl edit qgis-server@.service`. Без `sudo` записать файл нельзя.
2. Редактор открывает временный файл (имя вида `.#override.conf...`). Сохранять нужно его, имя не менять.
   - **nano:** Ctrl+O, nano покажет «File Name to Write: …» — нажать Enter, не меняя имени. Затем Ctrl+X.
   - **vim:** Esc, затем `:wq` и Enter.
3. Изменение записывается в `override.conf` только после закрытия редактора. В терминале должно появиться «Successfully installed edited file '/etc/systemd/system/qgis-server@.service.d/override.conf'».

Если появляется другое сообщение — пришлите его.

**Проще: в вашем unit уже есть `EnvironmentFile=/etc/qgis-server/env`**
Переменные можно дописать в этот файл. Тогда drop-in не нужен.
```bash
sudo tee -a /etc/qgis-server/env >/dev/null <<'EOF'
QGIS_PLUGINPATH=/opt/qgis-server/plugins
OTDR_PG_SERVICE=gisdb
OTDR_PROJECT=q2s
EOF
sudo systemctl restart 'qgis-server@*.service'
```
В этом файле формат `KEY=value`, без слова `Environment=` и без `[Service]`.

Если `QGIS_PLUGINPATH` в `/etc/qgis-server/env` уже задан, второй строки не добавляйте. Допишите путь к существующему значению через двоеточие, например `QGIS_PLUGINPATH=/старый/путь:/opt/qgis-server/plugins`.
```bash
grep -n QGIS_PLUGINPATH /etc/qgis-server/env
```

**Записать drop-in без редактора**
Если нужен именно drop-in:
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
Используйте один способ: `/etc/qgis-server/env` или drop-in. Если одна переменная задана в обоих, действует значение из drop-in.

---

## 10. Пользователь

Сделай .markdown по диалогу

## 10. Ассистент

Файл `otdr_marks.md` прикреплён выше; он же в ветке `claude/qgis-snmp-trap-plugin-9t4s6k` (коммит `8f40fd8`). Получить на сервере:
```bash
cd /tmp/uv && git pull
```

Это не стенограмма, а итоговое руководство по диалогу с вашими значениями (`gisdb`, `q2s`, `qgis-server@.service`). Разделы:
- как работает плагин;
- установка и обновление;
- переменные окружения: через `/etc/qgis-server/env` или drop-in, как сохранить в `systemctl edit`;
- как проверить, что переменные дошли до процесса;
- перенос `pg_service.conf` из папки Windows на сервер, права;
- особенность FastCGI с окружением процесса и её исправление в плагине;
- что сделать один раз после первого запуска (перезапуск, перегенерация конфигурации QWC, права);
- замечания по работе плагина.

---

## 11. Пользователь

> стенограмм

Нужна стенограмма

## 11. Ассистент

Стенограмма — этот файл, `otdr_marks_transcript.md`.
