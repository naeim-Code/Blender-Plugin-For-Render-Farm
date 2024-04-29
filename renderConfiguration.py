from __future__ import unicode_literals, print_function, division, absolute_import
import sys
PY2 = sys.version_info.major == 2

if PY2:
    # default open function in python 3
    from io import open
    # python2's stdlib ConfigParser is extremely limited.
    # It has neither read_string() nor read_dict() methods
    # and doesn't handle unicode well.
    from backports.configparser import ConfigParser
else:
    from configparser import ConfigParser

if False:
    from typing import Dict

class Config(ConfigParser):
    def __init__(self):  # type: () -> None
        ConfigParser.__init__(self, strict=False, interpolation=None)
        self.optionxform = lambda opt: opt  # type: ignore

    @staticmethod
    def from_filepath(file_):  # type: (str) -> Config
        with open(file_, "r", encoding="utf-8-sig", errors="replace") as f:
            data = f.read()
            cfg = Config()
            cfg.read_string(data, source=file_)
            return cfg

    def clone(self):  # type: () -> Config
        new_cfg = Config()
        new_cfg.read_dict(self)
        return new_cfg

    def pop_section(self, section):  # type: (str) -> Dict[str, str]
        """
        Removes `section` and returns the dictionary equivalent to the section's
        key-value pairs.

        Workaround for broken pop() behaviour of ConfigParser.
        """
        # The section returned from .pop() is useless as any indexing on it
        # tries to reference the section of its own name from the ConfigParser
        # from which it was just removed.
        # Regular indexing throws exceptions and .get() always returns None
        list_section = dict(self[section].items())
        self.pop(section)
        return list_section

    def is_empty(self):  # type: () -> bool
        return self == Config()

    def flattened(self):  # type: (Config) -> Dict[str, str]
        return {
            key: val
            for section_name, section in self.items()
            for key, val in section.items()
            if not section_name.startswith("IGNORE_")
        }

    def write_to_file(self, path):  # type: (str) -> None
        with open(path, "w", encoding="utf-8") as cfg_file:
            self.write(cfg_file, False)

