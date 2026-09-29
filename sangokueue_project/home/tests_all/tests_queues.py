from collections import defaultdict
from contextlib import nullcontext
from unittest.mock import patch

from django.test import SimpleTestCase

from home import queues
from home.models import Billet


class _Horloge:
    def __init__(self, maintenant=1_000_000.0):
        self.maintenant = maintenant

    def time(self):
        return self.maintenant

    def avancer(self, secondes):
        self.maintenant += secondes


class _FakeRedis:
    def __init__(self):
        self._zsets = defaultdict(dict)
        self._kv = {}

    def zadd(self, name, mapping):
        self._zsets[name].update(
            {str(membre): float(score) for membre, score in mapping.items()}
        )
        return len(mapping)

    def zrange(self, name, start, end, withscores=False):
        items = sorted(
            self._zsets[name].items(),
            key=lambda item: (item[1], item[0]),
        )
        if not items:
            return []
        fin = None if end < 0 else end + 1
        extraits = items[start:fin]
        if withscores:
            return extraits
        return [membre for membre, _score in extraits]

    def zpopmin(self, name, count=1):
        items = sorted(
            self._zsets[name].items(),
            key=lambda item: (item[1], item[0]),
        )
        extraits = items[:count]
        for membre, _score in extraits:
            del self._zsets[name][membre]
        if not self._zsets[name]:
            self._zsets.pop(name, None)
        return extraits

    def zrangebyscore(self, name, min, max):
        return [
            membre
            for membre, score in self._zsets[name].items()
            if float(min) <= score <= float(max)
        ]

    def zrem(self, name, *values):
        retires = 0
        store = self._zsets[name]
        for valeur in values:
            if valeur in store:
                del store[valeur]
                retires += 1
        if name in self._zsets and not self._zsets[name]:
            del self._zsets[name]
        return retires

    def delete(self, *names):
        retires = 0
        for name in names:
            existait = name in self._zsets or name in self._kv
            self._zsets.pop(name, None)
            self._kv.pop(name, None)
            if existait:
                retires += 1
        return retires

    def exists(self, name):
        return int(name in self._kv or name in self._zsets)

    def set(self, name, value):
        self._kv[name] = value
        return True

    def lock(self, *args, **kwargs):
        return nullcontext()


class TestQueues(SimpleTestCase):
    def setUp(self):
        queues._client = _FakeRedis()
        self.horloge = _Horloge()
        self.time_patcher = patch("home.queues.time.time", self.horloge.time)
        self.time_patcher.start()
        self.file = "attraction"

    def tearDown(self):
        self.time_patcher.stop()
        queues._client = None

    def _entrer(self, ticket_id, priorite):
        queues.append_to_queue(self.file, ticket_id, priorite)

    def test_file_vide_pop_retourne_none(self):
        self.assertIsNone(queues.pop_from_queue(self.file))

    def test_humain_seul_est_appele(self):
        self._entrer("H1", Billet.Priorite.HUMAN)

        self.assertEqual(queues.pop_from_queue(self.file), "H1")

    def test_super_saiyan_passe_avant_les_autres(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.horloge.avancer(10)
        self._entrer("S1", Billet.Priorite.SAIYAN)
        self.horloge.avancer(10)
        self._entrer("SS1", Billet.Priorite.SUPER_SAIYAN)

        self.assertEqual(queues.pop_from_queue(self.file), "SS1")

    def test_super_saiyan_a_chaque_appel(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.horloge.avancer(1)
        self._entrer("SS1", Billet.Priorite.SUPER_SAIYAN)
        self.horloge.avancer(1)
        self._entrer("S1", Billet.Priorite.SAIYAN)
        self.horloge.avancer(1)
        self._entrer("SS2", Billet.Priorite.SUPER_SAIYAN)

        self.assertEqual(queues.pop_from_queue(self.file), "SS1")
        self.assertEqual(queues.pop_from_queue(self.file), "SS2")
        self.assertEqual(queues.pop_from_queue(self.file), "H1")

    def test_plus_ancien_entre_saiyan_et_humain(self):
        self._entrer("S1", Billet.Priorite.SAIYAN)
        self.horloge.avancer(30)
        self._entrer("H1", Billet.Priorite.HUMAN)

        self.assertEqual(queues.pop_from_queue(self.file), "S1")

    def test_humain_plus_ancien_passe_si_saiyan_sous_25_min(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.horloge.avancer(60)
        self._entrer("S1", Billet.Priorite.SAIYAN)
        self.horloge.avancer(60)

        self.assertEqual(queues.pop_from_queue(self.file), "H1")

    def test_saiyan_passe_apres_25_min_meme_si_humain_plus_ancien(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.horloge.avancer(60)
        self._entrer("S1", Billet.Priorite.SAIYAN)
        self.horloge.avancer(queues.SAIYAN_PRIORITY_WAIT_SECONDS + 1)

        self.assertEqual(queues.pop_from_queue(self.file), "S1")

    def test_fifo_dans_la_meme_file(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.horloge.avancer(5)
        self._entrer("H2", Billet.Priorite.HUMAN)

        self.assertEqual(queues.pop_from_queue(self.file), "H1")
        self.assertEqual(queues.pop_from_queue(self.file), "H2")

    def test_pause_bloque_le_pop(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        queues.pause_queue(self.file, True)

        self.assertTrue(queues.is_paused(self.file))
        self.assertIsNone(queues.pop_from_queue(self.file))

        queues.pause_queue(self.file, False)

        self.assertFalse(queues.is_paused(self.file))
        self.assertEqual(queues.pop_from_queue(self.file), "H1")

    def test_validation_dans_les_10_min(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.assertEqual(queues.pop_from_queue(self.file), "H1")

        self.horloge.avancer(queues.CALLED_WAIT_SECONDS - 1)

        self.assertTrue(queues.validate_entry(self.file, "H1"))

    def test_expire_apres_10_min_sans_validation(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.assertEqual(queues.pop_from_queue(self.file), "H1")

        self.horloge.avancer(queues.CALLED_WAIT_SECONDS + 1)

        self.assertEqual(queues.expire_called(self.file), ["H1"])
        self.assertFalse(queues.validate_entry(self.file, "H1"))

    def test_validation_refusee_apres_expiration(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self.assertEqual(queues.pop_from_queue(self.file), "H1")

        self.horloge.avancer(queues.CALLED_WAIT_SECONDS + 1)

        self.assertFalse(queues.validate_entry(self.file, "H1"))

    def test_remove_from_queue(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self._entrer("H2", Billet.Priorite.HUMAN)
        queues.remove_from_queue(self.file, "H1")

        self.assertEqual(queues.pop_from_queue(self.file), "H2")
        self.assertIsNone(queues.pop_from_queue(self.file))

    def test_clear_queue(self):
        self._entrer("H1", Billet.Priorite.HUMAN)
        self._entrer("SS1", Billet.Priorite.SUPER_SAIYAN)
        queues.pause_queue(self.file, True)
        queues.clear_queue(self.file)

        self.assertFalse(queues.is_paused(self.file))
        self.assertIsNone(queues.pop_from_queue(self.file))
