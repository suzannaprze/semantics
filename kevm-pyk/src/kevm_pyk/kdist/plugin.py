from __future__ import annotations

import sys
from distutils.dir_util import copy_tree
from typing import TYPE_CHECKING

from pyk.kbuild.utils import k_version, sync_files
from pyk.kdist.api import Target
from pyk.kllvm.compiler import compile_kllvm, compile_runtime
from pyk.utils import run_process_2

from .. import config
from ..kompile import KompileTarget, kevm_kompile, lib_ccopts

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path
    from typing import Any, Final


class KEVMTarget(Target):
    _kompile_args: dict[str, Any]

    def __init__(self, kompile_args: Mapping[str, Any]):
        self._kompile_args = dict(kompile_args)

    def build(self, output_dir: Path, deps: dict[str, Path], args: dict[str, Any], verbose: bool) -> None:
        llvm_proof_hint_debugging = bool(args.get('llvm-proof-hint-debugging', ''))
        llvm_proof_hint_instrumentation = bool(args.get('llvm-proof-hint-instrumentation', ''))
        enable_llvm_debug = bool(args.get('enable-llvm-debug', ''))
        debug_build = bool(args.get('debug-build', ''))
        ccopts = [ccopt for ccopt in args.get('ccopts', '').split(' ') if ccopt]

        kevm_kompile(
            output_dir=output_dir,
            enable_llvm_debug=enable_llvm_debug,
            verbose=verbose,
            ccopts=ccopts,
            plugin_dir=deps['evm-semantics.plugin'],
            debug_build=debug_build,
            llvm_proof_hint_debugging=llvm_proof_hint_debugging,
            llvm_proof_hint_instrumentation=llvm_proof_hint_instrumentation,
            **self._kompile_args,
        )

    def deps(self) -> tuple[str, ...]:
        return ('evm-semantics.plugin',)

    def source(self) -> tuple[Path, ...]:
        return (config.EVM_SEMANTICS_DIR,) + tuple(config.MODULE_DIR.rglob('*.py'))

    def context(self) -> dict[str, str]:
        return {'k-version': k_version().text}


class PluginTarget(Target):
    def build(self, output_dir: Path, deps: dict[str, Any], args: dict[str, Any], verbose: bool) -> None:
        sync_files(
            source_dir=config.PLUGIN_DIR / 'plugin-c',
            target_dir=output_dir / 'plugin-c',
            file_names=[
                'blake2.h',
                'crypto.cpp',
                'plugin_util.cpp',
                'plugin_util.h',
            ],
        )

        copy_tree(str(config.PLUGIN_DIR), '.')
        run_process_2(['make', 'libcryptopp', 'libff', 'blake2', '-j8'])

        copy_tree('./build/libcryptopp', str(output_dir / 'libcryptopp'))
        copy_tree('./build/libff', str(output_dir / 'libff'))
        copy_tree('./build/blake2', str(output_dir / 'blake2'))

    def source(self) -> tuple[Path]:
        return (config.PLUGIN_DIR,)


class KLLVMTarget(Target):
    def build(self, output_dir: Path, deps: dict[str, Path], args: dict[str, Any], verbose: bool) -> None:
        compile_kllvm(output_dir, verbose=verbose)

    def context(self) -> dict[str, str]:
        return {
            'k-version': k_version().text,
            'python-path': sys.executable,
            'python-version': sys.version,
        }


class KLLVMRuntimeTarget(Target):
    def build(self, output_dir: Path, deps: dict[str, Path], args: dict[str, Any], verbose: bool) -> None:
        compile_runtime(
            definition_dir=deps['evm-semantics.llvm'],
            target_dir=output_dir,
            ccopts=lib_ccopts(deps['evm-semantics.plugin']),
            verbose=verbose,
        )

    def deps(self) -> tuple[str, ...]:
        return ('evm-semantics.plugin', 'evm-semantics.llvm')

    def source(self) -> tuple[Path, ...]:
        return (config.EVM_SEMANTICS_DIR,) + tuple(config.MODULE_DIR.rglob('*.py'))

    def context(self) -> dict[str, str]:
        return {
            'k-version': k_version().text,
            'python-path': sys.executable,
            'python-version': sys.version,
        }


__TARGETS__: Final = {
    'llvm': KEVMTarget(
        {
            'target': KompileTarget.LLVM,
            'main_file': config.EVM_SEMANTICS_DIR / 'driver.md',
            'main_module': 'ETHEREUM-SIMULATION',
            'syntax_module': 'ETHEREUM-SIMULATION',
            'optimization': 3,
        },
    ),
    'haskell': KEVMTarget(
        {
            'target': KompileTarget.HASKELL,
            'main_file': config.EVM_SEMANTICS_DIR / 'edsl.md',
            'main_module': 'EDSL',
            'syntax_module': 'EDSL',
        },
    ),
    'haskell-standalone': KEVMTarget(
        {
            'target': KompileTarget.HASKELL,
            'main_file': config.EVM_SEMANTICS_DIR / 'driver.md',
            'main_module': 'ETHEREUM-SIMULATION',
            'syntax_module': 'ETHEREUM-SIMULATION',
        },
    ),
    'plugin': PluginTarget(),
    'kllvm': KLLVMTarget(),
    'kllvm-runtime': KLLVMRuntimeTarget(),
}
