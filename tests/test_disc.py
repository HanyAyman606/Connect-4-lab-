"""Unit tests for core.owner and core.disc."""

import copy
import pickle
import unittest
from concurrent.futures import ProcessPoolExecutor

from core.disc import Disc, EMPTY_DISC
from core.owner import Owner


def _is_shared_in_worker(disc):
    """Runs in another process: the received disc must be that process's shared disc."""
    return disc is Disc(disc.owner, disc.color)


class OwnerTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual((Owner.EMPTY, Owner.HUMAN, Owner.COMPUTER), (0, 1, 2))


class DiscTests(unittest.TestCase):
    def test_same_key_gives_same_object(self):
        self.assertIs(Disc(Owner.HUMAN, "red"), Disc(Owner.HUMAN, "red"))

    def test_different_color_or_owner_gives_different_object(self):
        self.assertIsNot(Disc(Owner.HUMAN, "red"), Disc(Owner.HUMAN, "blue"))
        self.assertIsNot(Disc(Owner.HUMAN, "red"), Disc(Owner.COMPUTER, "red"))

    def test_plain_int_owner_is_normalised(self):
        self.assertIs(Disc(1, "red"), Disc(Owner.HUMAN, "red"))

    def test_empty_disc(self):
        self.assertTrue(EMPTY_DISC.is_empty)
        self.assertIs(EMPTY_DISC, Disc(Owner.EMPTY))
        self.assertIsNone(EMPTY_DISC.color)
        self.assertFalse(EMPTY_DISC.belongs_to(Owner.HUMAN))
        self.assertEqual(EMPTY_DISC.symbol, ".")

    def test_player_disc(self):
        disc = Disc(Owner.COMPUTER, "yellow")
        self.assertFalse(disc.is_empty)
        self.assertTrue(disc.belongs_to(Owner.COMPUTER))
        self.assertFalse(disc.belongs_to(Owner.HUMAN))
        self.assertEqual(disc.key, (Owner.COMPUTER, "yellow"))
        self.assertEqual(str(disc), "O")

    def test_validation(self):
        with self.assertRaises(ValueError):
            Disc(Owner.HUMAN)                    # player disc needs a color
        with self.assertRaises(ValueError):
            Disc(Owner.HUMAN, "")                # empty color key
        with self.assertRaises(ValueError):
            Disc(Owner.EMPTY, "red")             # empty disc has no color
        with self.assertRaises(ValueError):
            Disc(5, "red")                       # not a valid owner

    def test_immutable(self):
        disc = Disc(Owner.HUMAN, "red")
        with self.assertRaises(AttributeError):
            disc._color = "blue"
        with self.assertRaises(AttributeError):
            disc.radius = 10
        with self.assertRaises(AttributeError):
            del disc._owner

    def test_copy_and_pickle_keep_the_shared_object(self):
        disc = Disc(Owner.HUMAN, "red")
        self.assertIs(copy.copy(disc), disc)
        self.assertIs(copy.deepcopy(disc), disc)
        self.assertIs(pickle.loads(pickle.dumps(disc)), disc)
        self.assertIs(pickle.loads(pickle.dumps(EMPTY_DISC)), EMPTY_DISC)

    def test_hashable_in_a_tuple_board(self):
        row = (EMPTY_DISC, Disc(Owner.HUMAN, "red"))
        self.assertEqual(hash(row), hash((EMPTY_DISC, Disc(Owner.HUMAN, "red"))))

    def test_shared_across_processes(self):
        disc = Disc(Owner.COMPUTER, "yellow")
        with ProcessPoolExecutor(max_workers=1) as pool:
            self.assertTrue(pool.submit(_is_shared_in_worker, disc).result())


if __name__ == "__main__":
    unittest.main()
