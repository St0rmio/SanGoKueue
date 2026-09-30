import time

from django.db.backends.postgresql.base import DatabaseWrapper as PostgresWrapper

TENTATIVES = 5


def avec_reessai(action, tentatives=TENTATIVES):
    """Réessaie quand Render coupe la connexion au réveil de Postgres."""
    attente = 0.5
    for numero in range(tentatives):
        try:
            return action()
        except Exception as exc:
            if type(exc).__name__ != "OperationalError" or numero == tentatives - 1:
                raise
            time.sleep(attente)
            attente = min(attente * 2, 4)


class DatabaseWrapper(PostgresWrapper):
    def get_new_connection(self, conn_params):
        ouvrir = super().get_new_connection
        return avec_reessai(lambda: ouvrir(conn_params))
