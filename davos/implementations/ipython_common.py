"""
This module contains implementations of helper functions common across
all IPython versions and front-end interfaces.
"""

__all__ = []


import sys
import textwrap
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from subprocess import CalledProcessError

from IPython.utils.process import system as _run_shell_cmd

from davos import config
from davos.core.exceptions import DavosParserError


def _check_conda_avail_helper():
    """
    Check whether the `conda` executable is available.

    `IPython` implementation of the helper function for
    `davos.core.core.check_conda`. Runs a command shell (`conda list
    IPython`) whose stdout contains the path to the current conda
    environment, which can be parsed by the main `check_conda` function.
    Uses the `%conda` IPython line magic, if available (usually if
    `IPython>=7.3`). Otherwise, looks for `conda` history file and runs
    some logic to determine whether -- if the `conda` exe is available,
    whether `davos` is running from the base environment or not, and if
    not, passes the `--prefix` to the command. If successful, returns
    the (suppressed) stdout generated by the command. Otherwise, returns
    `None`.

    Returns
    -------
    str or None
        If the command runs successfully, the captured stdout.
        Otherwise, `None`.

    See Also
    --------
    davos.core.core.check_conda : core function that calls this helper.
    """
    if 'conda' in set(config._ipython_shell.magics_manager.magics['line']):
        # if the %conda line magic is available (IPython>=7.3), use that
        # directly
        try:
            with redirect_stdout(StringIO()) as conda_list_output:
                config._ipython_shell.run_line_magic('conda', 'list IPython')
        except ValueError:
            # kernel is not running within a conda environment
            return None

    else:
        conda_history_path = Path(sys.prefix, "conda-meta", "history")
        # if conda history file doesn't exist at this location, davos
        # isn't running in a conda environment
        if not conda_history_path.is_file():
            return None

        cmd = "conda list IPython"
        # location we'd expect to find conda executable if davos is
        # running in the 'base' environment (and no prefix is needed)
        base_exe_loc = Path(sys.executable).parent.joinpath('conda')

        if not base_exe_loc.is_file():
            cmd += f" --prefix {sys.prefix}"

        with redirect_stdout(StringIO()) as conda_list_output:
            _run_shell_cmd(cmd)

    return conda_list_output.getvalue()


def _run_shell_command_helper(command):
    """
    Run a shell command in a subprocess, piping stdout & stderr.

    `IPython` implementation of helper function for
    `davos.core.core.run_shell_command`. stdout & stderr streams are
    captured or suppressed by the outer function. If the command runs
    successfully, return its exit status (`0`). Otherwise, raise an
    error.

    Parameters
    ----------
    command : str
        The command to execute.

    Returns
    -------
    int
        The exit code of the command. This will always be `0` if the
        function returns. Otherwise, an error is raised.

    Raises
    ------
    subprocess.CalledProcessError :
        If the command returned a non-zero exit status.

    See Also
    --------
    IPython.utils.process.system : `IPython` shell command runner.
    """
    retcode = _run_shell_cmd(command)
    if retcode != 0:
        raise CalledProcessError(returncode=retcode, cmd=command)


def _set_custom_showsyntaxerror():
    """
    Overload the `IPython` shell's `.showsyntaxerror()` method.

    Replaces the global `IPython` interactive shell object's
    `.showsyntaxerror()` method with a custom function that allows
    `davos`-native exceptions raised during the pre-execution cell
    parsing phase to display a full traceback. Also:
        - updates the custom function's docstring to include the
          original `.showsyntaxerror()` method's docstring and
          explicitly note that the method was updated by `davos`
        - stores a reference to the original `.showsyntaxerror()` method
          in the `davos.config` object so it can be called from the
          custom version
        - binds the custom function to the interactive shell object
          *instance* so it implicitly receives the instance as its first
          argument when called (like a normal instance method)

    See Also
    -------
    davos.implementations.ipython_common._showsyntaxerror_davos :
        The custom `.showsyntaxerror()` method set by `davos`.
    IPython.core.interactiveshell.InteractiveShell.showsyntaxerror :
        The original, overloaded `.showsyntaxerror()` method.

    Notes
    -----
    Runs exactly once when `davos` is imported and initialized in an
    `IPython` environment, and takes no action if run again. This
    prevents overwriting the reference to the original
    `.showsyntaxerror()` method stored in the `davos.config` object.
    """
    if config._ipy_showsyntaxerror_orig is not None:
        # function has already been called
        return

    ipy_shell = config.ipython_shell
    new_doc = textwrap.dedent(f"""\
        {' METHOD UPDATED BY DAVOS PACKAGE '.center(72, '=')}
        
        {textwrap.indent(_showsyntaxerror_davos.__doc__, '    ')}

        {' ORIGINAL DOCSTRING: '.center(72, '=')}
        
        
        {ipy_shell.showsyntaxerror.__doc__}""")

    _showsyntaxerror_davos.__doc__ = new_doc
    config._ipy_showsyntaxerror_orig = ipy_shell.showsyntaxerror
    # bind function as method
    # pylint: disable=no-value-for-parameter
    # (pylint bug: expects __get__ method to take same args as function)
    ipy_shell.showsyntaxerror = _showsyntaxerror_davos.__get__(ipy_shell,
                                                               type(ipy_shell))


# noinspection PyUnusedLocal
def _showsyntaxerror_davos(
        ipy_shell,
        filename=None,
        running_compiled_code=False    # pylint: disable=unused-argument
):
    """
    Show `davos` library `SyntaxError` subclasses with full tracebacks.


    Replaces global IPython interactive shell object's
    `.showsyntaxerror()` method during initialization as a way to hook
    into `IPython`'s exception handling machinery for errors raised
    during the pre-execution cell parsing phase.

    Because cell content is parsed as text rather than actually executed
    during this stage, the only exceptions `IPython` expects input
    transformers (such as the `davos` parser) to raise are
    `SyntaxError`s. Thus, all `davos` library exceptions that may be
    raised by the parser inherit from `SyntaxError`). And because
    `IPython` assumes any `SyntaxError`s raised during parsing were
    caused by issues with the cell content itself, it expects their
    stack traces to comprise only a single frame, and displays them in a
    format that does not include a full traceback. This function
    excludes `davos` library errors from this behavior, and displays
    them in full using the standard, more readable & informative format.

    Parameters
    ----------
    ipy_shell : IPython.core.interactiveshell.InteractiveShell
        The global `IPython` shell instance. Because the function is
        bound as a method of the shell instance, this is passed
        implicitly (i.e., equivalent to `self`).
    filename : str, optional
        The name of the file the `SyntaxError` occurred in. If `None`
        (default), the name of the cell's entry in `linecache.cache`
        will be used.
    running_compiled_code : bool, optional
        Whether the `SyntaxError` occurred while running compiled code
        (see **Notes** below).

    See Also
    --------
    davos.implementations.ipython_common._set_custom_showsyntaxerror :
        Replaces the `.showsyntaxerror()` method with this function.
    IPython.core.compilerop.code_name :
        Generates unique names for each cell used in `linecache.cache`.
    IPython.core.interactiveshell.InteractiveShell.showsyntaxerror :
        The original `.showsyntaxerror()` method this function replaces.


    Notes
    -----
    The `running_compiled_code` argument was added in `IPython` 6.1.0,
    and setting it to `True` accomplishes (something close to) the same
    thing this workaround does. However, since `davos` needs to support
    `IPython` versions back to v5.5.0, we can't rely on it being
    available.
    """
    etype, value, tb = ipy_shell._get_exc_info()
    if issubclass(etype, DavosParserError):
        try:
            # noinspection PyBroadException
            try:
                # display custom traceback, if class supports it
                stb = value._render_traceback_()
            except Exception:    # pylint: disable=broad-except
                stb = ipy_shell.InteractiveTB.structured_traceback(
                    etype, value, tb, tb_offset=ipy_shell.InteractiveTB.tb_offset
                )
            ipy_shell._showtraceback(etype, value, stb)
            if ipy_shell.call_pdb:
                ipy_shell.debugger(force=True)
        except KeyboardInterrupt:
            print('\n' + ipy_shell.get_exception_only(), file=sys.stderr)
        return None
    # original method is stored in Davos instance, but still bound
    # IPython.core.interactiveshell.InteractiveShell instance
    return config._ipy_showsyntaxerror_orig(filename=filename)
