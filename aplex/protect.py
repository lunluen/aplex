"""This module protects data in load balancers that is exposed to users."""

from collections.abc import Mapping, Sequence


class ReadOnlyMapping(Mapping):
    """Used to protect mapping objects such like dict."""

    def __init__(self, mapping):
        self._mapping = mapping

    def __len__(self):
        return self._mapping.__len__()

    def __iter__(self):
        return self._mapping.__iter__()

    def __getitem__(self, key):
        return self._mapping.__getitem__(key)


class ReadOnlySequence(Sequence):
    """Used to protect sequence objects such like list."""

    def __init__(self, sequence):
        self._sequence = sequence

    def __len__(self):
        return self._sequence.__len__()

    def __getitem__(self, index):
        return self._sequence.__getitem__(index)


def protect(target):
    if isinstance(target, Mapping):
        return ReadOnlyMapping(target)
    elif isinstance(target, Sequence):
        return ReadOnlySequence(target)
    else:
        raise TypeError('Unknown type to protect.')
