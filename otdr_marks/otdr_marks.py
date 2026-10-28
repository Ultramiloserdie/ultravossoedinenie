"""Метки обрывов OTDR для QGIS Server.

Один процесс QGIS Server на хосте в фоновом потоке опрашивает EVENTS_TABLE:
новая запись -> линейный слой проекта с именем refl_name -> точка на route_m
(или length_km) метров от начала трассы -> EVENTS_TABLE.geom.
Метки рисует PostGIS-слой EVENTS_TABLE проекта: его добавляют в QGIS Desktop
со стилем otdr_events.qml (красный крест 45°, подпись). Проект плагин только читает.
"""
import ctypes
import os
import socket
import threading
import time
from urllib.parse import quote

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsDistanceArea,
    QgsExpression,
    QgsFeatureRequest,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
from qgis.server import QgsServerFilter

# Дано (OTDR_* - переменные окружения процесса QGIS Server)
PG_SERVICE = os.environ.get("OTDR_PG_SERVICE", "")  # сервис pg_service.conf с БД sasplanet_marks
PROJECT = os.environ.get("OTDR_PROJECT", "")        # имя проекта в PROJECT_SCHEMA.qgis_projects; "" - единственный
PROJECT_SCHEMA = "public"
EVENTS_TABLE = "otdr.events"
EVENTS_SRID = 3395              # SRID колонки geom (Яндекс)
POLL_SEC = 5                    # опрос таблицы
WORK_TIMEOUT = "10 minutes"     # status = 'work' дольше: обработчик упал, событие берётся заново
ORDER_FIELD = None              # поле порядка участков трассы
CABLE_FACTOR = 1.0              # оптическая длина волокна больше физической? 1.02-1.07?
START_OFFSET_M = 0.0            # волокно до начала трассы, м
SNAP_TOL_M = 5.0                # допуск стыковки участков, м
DEFAULT_ELLIPSOID = "EPSG:7030"

_FAST = Qgis.ProjectReadFlags(Qgis.ProjectReadFlag.DontResolveLayers) | Qgis.ProjectReadFlag.DontLoadLayouts
_CLAIM = """UPDATE {t} SET {st} = 'work', processed_at = now()
WHERE id IN (SELECT id FROM {t}
             WHERE {st} IS NULL OR ({st} = 'work' AND processed_at < now() - interval '{timeout}')
             ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED)
RETURNING id, refl_name, length_km, route_m"""

# libfcgi (FCGI_Accept) подменяет environ параметрами запроса и освобождает их в начале
# следующего FCGI_Accept: до нового запроса getenv() фонового потока (libpq, PROJ) читал бы
# освобождённую память без переменных процесса (PGSERVICEFILE и т.п.).
_LIBC = ctypes.CDLL(None)
_LIBC.getenv.restype = ctypes.c_char_p
_ENVIRON = ctypes.c_void_p.in_dll(_LIBC, "environ")
_ENV_COPY = (ctypes.c_char_p * (len(os.environb) + 1))(*(k + b"=" + v for k, v in os.environb.items()))


def _log(msg, level=Qgis.MessageLevel.Info):
    QgsMessageLog.logMessage(msg, "OTDR", level)


def _norm(s):
    s = (s or "").strip().lower()
    return s[:-4] if s.endswith(".sor") else s


def _val(v):
    """NULL из executeSql приходит как QVariant."""
    return None if v is None or isinstance(v, QVariant) and v.isNull() else v


def _km(value):
    return float(str(value).replace(",", ".").strip())


def _q(s):
    return "NULL" if not s else "'" + str(s).replace("'", "''") + "'"


def _single():
    """Один опрос на хост: абстрактный UNIX-сокет, освобождается при завершении процесса."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.bind(f"\0otdr_marks:{PG_SERVICE}:{PROJECT}")
        return s
    except OSError:
        s.close()
        return None


# --- БД ----------------------------------------------------------------------

def _pg():
    if not PG_SERVICE:
        raise LookupError("Не задан OTDR_PG_SERVICE")
    md = QgsProviderRegistry.instance().providerMetadata("postgres")
    return md.createConnection(f"service='{PG_SERVICE}'", {})


def _status_field(conn):
    """Колонка статуса: 'status' (референс) или 'stasus' (описание таблицы)."""
    schema, table = EVENTS_TABLE.split(".")
    cols = {r[0] for r in conn.executeSql(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema = {_q(schema)} AND table_name = {_q(table)}")}
    for c in ("status", "stasus"):
        if c in cols:
            return c
    raise LookupError(f"В {EVENTS_TABLE} нет колонки status")


def _project_uri(conn):
    """(имя, URI) проекта в PROJECT_SCHEMA.qgis_projects."""
    name = PROJECT
    if not name:
        names = [r[0] for r in conn.executeSql(f"SELECT name FROM {PROJECT_SCHEMA}.qgis_projects")]
        if len(names) != 1:
            raise LookupError(f"Проектов в {PROJECT_SCHEMA}.qgis_projects: {len(names)}, задайте OTDR_PROJECT")
        name = names[0]
    return name, (f"postgresql:?service={quote(PG_SERVICE, safe='')}"
                  f"&schema={quote(PROJECT_SCHEMA, safe='')}&project={quote(name, safe='')}")


# --- трасса --------------------------------------------------------------------

def _route_layer(prj, refl_name):
    """Линейный слой проекта, имя (или таблица) которого совпадает с refl_name."""
    key = _norm(refl_name)
    if not key:
        raise ValueError("Пустое название рефлектограммы")
    err = None
    for l in prj.mapLayers().values():
        if not isinstance(l, QgsVectorLayer) or key not in (
                _norm(l.name()), _norm(QgsDataSourceUri(l.source()).table())):
            continue
        # в снимке проекта слои не загружены (DontResolveLayers)
        opts = QgsVectorLayer.LayerOptions()
        opts.loadDefaultStyle = False
        vl = QgsVectorLayer(l.source(), l.name(), l.providerType(), opts)
        if l.crs().isValid():
            vl.setCrs(l.crs())
        if not vl.isValid():
            err = f"Слой {l.name()!r} недоступен"
        elif vl.geometryType() != Qgis.GeometryType.Line:
            err = f"Слой {l.name()!r} не линейный"
        else:
            return vl
    if err:
        raise ValueError(err)
    raise LookupError(f"Трасса для рефлектограммы {refl_name!r} не найдена")


def _features(layer):
    req = QgsFeatureRequest()
    ordered = bool(ORDER_FIELD) and layer.fields().indexOf(ORDER_FIELD) >= 0
    if ordered:
        req.addOrderBy(QgsExpression.quotedColumnRef(ORDER_FIELD))
    feats = [f for f in layer.getFeatures(req) if f.hasGeometry()]
    if not ordered:
        feats.sort(key=lambda f: f.id())
    return feats


def _distance_area(prj, crs):
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


def locate(prj, refl_name, route_m):
    """(точка в СК слоя, СК слоя, примечание): route_m метров от начала трассы refl_name."""
    layer = _route_layer(prj, refl_name)
    parts = _parts(_features(layer))
    if not parts:
        raise ValueError(f"В слое {layer.name()!r} нет линейной геометрии")
    da = _distance_area(prj, layer.crs())
    route, rest = _chain(parts, da)
    pt, done = _walk(route, da, route_m)
    notes = []
    if route_m - done > 1e-6:
        notes.append(f"длина больше трассы на {route_m - done:.1f} м, метка в конце")
    if rest:
        notes.append(f"не пристыковано участков: {len(rest)}")
    return pt, layer.crs(), "; ".join(notes)


# --- слой меток в проекте --------------------------------------------------------

def _events_layers(prj):
    schema, table = EVENTS_TABLE.split(".")
    out = []
    for l in prj.mapLayers().values():
        u = QgsDataSourceUri(l.source())
        if l.providerType() == "postgres" and (u.schema(), u.table()) == (schema, table):
            out.append(l)
    return out


# --- опрос EVENTS_TABLE ------------------------------------------------------------

class _Poller(threading.Thread):
    """Фоновый опрос EVENTS_TABLE в процессе, который держит блокировку _single()."""

    def __init__(self, lock):
        super().__init__(name="otdr_marks", daemon=True)
        self.lock = lock
        self.conn = self.st = self.name = self.uri = self.dst = None
        self.prj = self.prj_ver = None
        self.err = None

    def run(self):
        while True:
            try:
                self.poll()
                self.err = None
            except Exception as e:
                if str(e) != self.err:  # повторяющаяся ошибка - одна запись в журнале
                    self.err = str(e)
                    _log(f"Опрос {EVENTS_TABLE}: {e}", Qgis.MessageLevel.Critical)
            time.sleep(POLL_SEC)

    def poll(self):
        if self.lock is None:
            self.lock = _single()
            if self.lock is None:
                return
        if self.conn is None:
            conn = _pg()
            self.st = _status_field(conn)
            self.name, self.uri = _project_uri(conn)
            self.dst = QgsCoordinateReferenceSystem(f"EPSG:{EVENTS_SRID}")
            self.conn = conn
            _log(f"Опрос {EVENTS_TABLE} запущен, проект {self.name!r}")
        prj = self.project()
        rows = self.conn.executeSql(_CLAIM.format(t=EVENTS_TABLE, st=self.st, timeout=WORK_TIMEOUT))
        for row in sorted(rows, key=lambda r: int(r[0])):
            self.process(prj, *map(_val, row))

    def project(self):
        """Снимок проекта без загрузки слоёв; перечитывается после сохранения проекта."""
        ver = self.conn.executeSql(
            f"SELECT metadata::text FROM {PROJECT_SCHEMA}.qgis_projects WHERE name = {_q(self.name)}")
        if self.prj is None or ver != self.prj_ver:
            prj = QgsProject()
            if not prj.read(self.uri, _FAST):
                raise RuntimeError(f"Не удалось прочитать проект {self.uri}: {prj.error()}")
            if not _events_layers(prj):
                _log(f"В проекте {self.name!r} нет слоя {EVENTS_TABLE}: метки не видны. "
                     "Добавьте слой в QGIS Desktop, стиль otdr_events.qml", Qgis.MessageLevel.Warning)
            self.prj, self.prj_ver = prj, ver
        return self.prj

    def process(self, prj, eid, name, length_km, route_m):
        eid = int(eid)
        try:
            if route_m is None:
                if length_km is None:
                    raise ValueError("Нет length_km")
                route_m = max(0.0, (_km(length_km) * 1000.0 - START_OFFSET_M) / CABLE_FACTOR)
            route_m = float(route_m)
            pt, crs, note = locate(prj, name, route_m)
            p = QgsCoordinateTransform(crs, self.dst, prj).transform(pt)
            self.conn.executeSql(
                f"UPDATE {EVENTS_TABLE} SET {self.st} = 'ok', processed_at = now(), "
                f"route_m = {route_m!r}, note = {_q(note)}, "
                f"geom = ST_SetSRID(ST_MakePoint({p.x()!r}, {p.y()!r}), {EVENTS_SRID}) WHERE id = {eid}")
            _log(f"#{eid} {name}: {route_m:.1f} м по трассе" + (f" ({note})" if note else ""),
                 Qgis.MessageLevel.Warning if note else Qgis.MessageLevel.Info)
        except Exception as e:
            self.conn.executeSql(
                f"UPDATE {EVENTS_TABLE} SET {self.st} = 'error', processed_at = now(), "
                f"note = {_q(e)} WHERE id = {eid}")
            _log(f"#{eid} {name}: {e}", Qgis.MessageLevel.Critical)


class _ProcessEnviron(QgsServerFilter):
    """После ответа возвращает environ к копии окружения процесса (_ENV_COPY)."""

    def onResponseComplete(self):
        if _LIBC.getenv(b"FCGI_ROLE"):  # environ - параметры запроса FastCGI
            _ENVIRON.value = ctypes.addressof(_ENV_COPY)
        return True


class OtdrMarks:
    """Серверный плагин: фоновый опрос EVENTS_TABLE."""

    def __init__(self, server_iface):
        self.server_iface = server_iface
        self.environ_filter = _ProcessEnviron(server_iface)
        server_iface.registerFilter(self.environ_filter, 10000)  # последним: другим фильтрам нужен environ запроса
        self.poller = _Poller(_single())
        self.poller.start()
