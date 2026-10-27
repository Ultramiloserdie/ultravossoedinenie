def serverClassFactory(serverIface):  # noqa: N802
    from .otdr_marks import OtdrMarks
    return OtdrMarks(serverIface)
