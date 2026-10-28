"""Открывает проект так же, как QGIS Server при запросе, и печатает слои, которые сервер не загрузит.

Из-за любого такого слоя QGIS Server на все запросы к проекту отвечает «Layer(s) not valid»
(если не задан QGIS_SERVER_IGNORE_BAD_LAYERS=1). env -i - окружение запроса FastCGI:
переменных из unit systemd (PGSERVICEFILE и т.п.) в нём нет.

    sudo -u www-data env -i QT_QPA_PLATFORM=offscreen /usr/bin/python3 check_project.py \\
        'postgresql:?service=gisdb&schema=public&project=q2s'
"""
import os
import shutil
import sys
import tempfile

from qgis.core import Qgis, QgsApplication, QgsProject


def main(uri):
    tmp = tempfile.mkdtemp(prefix="otdr_check_")  # профиль QGIS: домашний каталог www-data недоступен для записи
    os.environ.setdefault("XDG_RUNTIME_DIR", tmp)
    os.environ.setdefault("QGIS_CUSTOM_CONFIG_PATH", tmp)
    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()
    msgs = []

    def collect(msg, tag, level):
        if level >= Qgis.MessageLevel.Warning:
            msgs.append(f"  [{tag}] {msg}")

    app.messageLog().messageReceived.connect(collect)
    # как QgsConfigCache::project() в QGIS Server
    prj = QgsProject(None, Qgis.ProjectCapabilities())
    QgsProject.setInstance(prj)
    ok = prj.read(uri, Qgis.ProjectReadFlags(Qgis.ProjectReadFlag.DontStoreOriginalStyles)
                  | Qgis.ProjectReadFlag.DontLoad3DViews)
    bad = [l for l in prj.mapLayers().values() if not l.isValid()]
    if not ok:
        print(f"Проект не читается: {prj.error()}")
    for l in bad:
        print(f"Не загружается: {l.name()!r} (id {l.id()}, {l.providerType()}): {l.publicSource()}")
    print(*dict.fromkeys(msgs), sep="\n")
    if ok:
        print(f"Слоёв: {len(prj.mapLayers())}, не загружаются: {len(bad)}")
    prj.clear()
    app.exitQgis()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok and not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
