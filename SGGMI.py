"""
Mod Importer for SuperGiant Games' Games

https://github.com/MagicGonads/sgg-mod-format
"""

__all__ = [
    # functions
    "main",
    "configure_globals",
    "start",
    "preplogfile",
    "cleanup",
    "hashfile",
    "lua_addimport",
    # modules
    "logging",
    "xml",
    "sjson",
    "json",
    "hashlib",
]
__version__ = "1.0a-r4"
__author__ = "Andre Issa"

# Dependencies

import os, sys, stat
import logging
import json
import hashlib
from pathlib import Path, PurePath
from shutil import copyfile, rmtree
from datetime import datetime
from collections import defaultdict
from distutils.dir_util import copy_tree
from distutils.errors import DistutilsFileError

from sggmi import (
    args_parser,
    util,
    messages,
    modfile,
)
from sggmi.config import SggmiConfiguration
from sggmi.util import (
    alt_exit,
    alt_input,
    alt_open,
    alt_print,
    alt_warn,
)

def deploy_mods(todeploy, config):
    for file_path in todeploy.keys():
        PurePath.joinpath(
            config.deploy_dir,
            Path(file_path).resolve().parent.relative_to(config.mods_dir),
        ).mkdir(parents=True, exist_ok=True)

        copyfile(
            Path(file_path),
            PurePath.joinpath(
                config.deploy_dir, Path(file_path).relative_to(config.mods_dir)
            ),
        )


def sort_mods(base, mods, codes):
    codes[base].sort(key=lambda x: x.load["priority"])
    for i in range(len(mods)):
        mods[i].id = i


def make_base_edits(base, payloads, config):
    PurePath.joinpath(config.base_cache_dir, Path(base).parent).mkdir(
        parents=True, exist_ok=True
    )
    copyfile(
        PurePath.joinpath(config.scope_dir, base),
        PurePath.joinpath(config.base_cache_dir, base),
    )

    if config.echo:
        i = 0
        alt_print(f"\n{base}", config=config)

    try:
        for payload in payloads:
            payload.act(
                PurePath.joinpath(config.scope_dir, base),
                payload.targets,
            )
            if config.echo:
                k = i + 1
                for s in payload.source.split("\n"):
                    i += 1
                    alt_print(
                        f" #{i}"
                        + " +" * (k < i)
                        + " " * ((k >= i) + 5 - len(str(i)))
                        + f"{Path(s).relative_to(config.mods_dir)}",
                        config=config,
                    )
    except Exception as e:
        copyfile(
            PurePath.joinpath(config.base_cache_dir, base),
            PurePath.joinpath(config.scope_dir, base),
        )
        raise RuntimeError(
            "Encountered uncaught exception while implementing mod changes"
        ) from e

    PurePath.joinpath(config.edit_cache_dir, Path(base).parent).mkdir(
        parents=True, exist_ok=True
    )
    util.hash_file(
        PurePath.joinpath(config.base_cache_dir, base),
        PurePath.joinpath(config.edit_cache_dir, f"{base}{config.edited_suffix}"),
    )


def cleanup(target, config):
    if not target and target.exists():
        return True

    if target.is_dir():
        empty = True
        for entry in target.iterdir():
            if cleanup(entry, config):
                empty = False
        if empty:
            target.rmdir()
            return False
        return True

    target_relative_to_base_cache_dir = target.relative_to(config.base_cache_dir)
    if PurePath.joinpath(config.scope_dir, target_relative_to_base_cache_dir).is_file():
        if util.is_edited(target_relative_to_base_cache_dir, config):
            copyfile(
                target,
                PurePath.joinpath(config.scope_dir, target_relative_to_base_cache_dir),
            )

        if config.echo:
            alt_print(target_relative_to_base_cache_dir, config=config)

        target.unlink()
        return False
    return True


def restorebase(config):
    if not cleanup(config.base_cache_dir, config):
        try:
            copy_tree(config.base_cache_dir, config.base_cache_dir)
        except DistutilsFileError:
            pass

def thetime():
    return datetime.now().strftime("%d.%m.%Y-%I.%M%p-%S.%f")


def preplogfile(config):
    if config.log:
        config.logs_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=config.logs_dir
            / f"{config.logs_prefix}{thetime()}{config.logs_suffix}",
            level=logging.INFO,
        )
    logging.captureWarnings(config.log and not config.echo)

# Main Process
def start(config):
    codes = defaultdict(list)
    todeploy = {}

    # remove anything in the base cache that is not in the edit cache
    alt_print(
        "\nCleaning edits... (if there are issues validate/reinstall files)",
        config=config,
    )
    restorebase(config)

    # remove the edit cache and base cache from the last run
    def on_error(func, path, exc_info):
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

    rmtree(config.edit_cache_dir, on_error)
    rmtree(config.base_cache_dir, on_error)

    config.edit_cache_dir.mkdir(parents=True, exist_ok=True)
    config.base_cache_dir.mkdir(parents=True, exist_ok=True)
    config.mods_dir.mkdir(parents=True, exist_ok=True)
    config.deploy_dir.mkdir(parents=True, exist_ok=True)

    alt_print("\nReading mod files...", config=config)
    for mod in config.mods_dir.iterdir():
        modfile_load(mod / config.mod_file, todeploy, config)

    deploy_mods(todeploy,config)

    chosen_profile = config.chosen_profile if config.chosen_profile else "empty profile"

    alt_print(f"\nModified files for {chosen_profile}:", config=config)
    for base, mods in codes.items():
        sort_mods(base, mods)
        make_base_edits(base, mods)

    bs = len(codes)
    ms = sum(map(len, codes.values()))

    alt_print(
        "\n"
        + str(bs)
        + " file"
        + ("s are", " is")[bs == 1]
        + " modified by"
        + " a total of "
        + str(ms)
        + " mod file"
        + "s" * (ms != 1)
        + ".",
        config=config,
    )


def main_action(config):
    try:
        start(config)
    except Exception as e:
        alt_print(
            "There was a critical error, now attempting to display the error",
            config=config,
        )
        alt_print(
            "(if this doesn't work, try again in a terminal"
            + " which doesn't close, or check the log files)",
            config=config,
        )
        logging.getLogger("MainExceptions").exception(e)
        alt_input("Press ENTER/RETURN to see the error...", config=config)
        raise RuntimeError("Encountered uncaught exception during program") from e

    alt_input("Press ENTER/RETURN to end program...", config=config)


if __name__ == "__main__":
    config = SggmiConfiguration( thisfile = __file__ )
    config.logger = logging.getLogger(__name__)

    parser = args_parser.get_parser()
    parsed_args = parser.parse_args()
    config.apply_command_line_arguments(parsed_args)

    scopes_okay = util.check_scopes(config)
    if not scopes_okay:
        if scopes_okay.message == "GameHasNoScope":
            alt_warn(
                messages.game_has_no_scope(
                    config.scope_dir, config.scope_dir.parent, config.config_file
                ), config=config
            )

        if scopes_okay.message == "DeployNotInScope":
            alt_warn(
                messages.deploy_not_in_scope(
                    config.deploy_dir, config.scope_dir, config.config_file
                ), config=config
            )

        alt_exit(1, config=config)

    if config.modify_config:
        alt_print("Config modification successful.", config=config)
        alt_exit(0, config=config)

    main_action(config)
