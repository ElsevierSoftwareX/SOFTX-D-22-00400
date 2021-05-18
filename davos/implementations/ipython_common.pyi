from typing import Literal, Optional, TypeVar
from ipykernel.zmqshell import ZMQInteractiveShell
from davos.core.core import PipInstallerKwargs

__all__ = list[Literal['check_conda', 'smuggle']]

_IpyShell = TypeVar('_IpyShell', bound=ZMQInteractiveShell)

def _run_shell_command_helper(command: str) -> None: ...
def _set_custom_showsyntaxerror() -> None: ...
def _showsyntaxerror_davos(
        ipy_shell: _IpyShell, 
        filename: Optional[str] = ..., 
        running_compiled_code: bool = ...
) -> None: ...
def check_conda() -> None: ...
def smuggle(
        name: str, 
        as_: Optional[str] = ..., 
        installer: Literal['conda', 'pip'] = ..., 
        args_str: str = ..., 
        installer_kwargs: Optional[PipInstallerKwargs] = ...
) -> None: ...