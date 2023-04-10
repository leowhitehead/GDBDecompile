#!/usr/bin/env python3

import gdb
import toml
import os
import shutil
import subprocess
import glob
from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import Terminal256Formatter

class GDBDecompile:
    
    def __init__(self):
        self.loaded = False #set to True when extension loads without errors
        self.options = self._loadConfig()
        self.decompiled = False #set to True after target has been decompiled
    
    def display(self, message: str):
        """
        Print a string output preceded by the coloured GDBCompile prompt
        """
        print(stringColour("GDBDecompile: ", PROMPT_COLOUR) + message)
    
    def execute(self, command: str) -> bool:
        """
        Wrapper for gdb.execute with error handling
        """
        try:
            gdb.execute(command)
            return True
        except Exception as e:
            self.display(f"ERROR: {e}")
            return False
    
    def executeCapture(self, command: str) -> str | None:
        """
        Run gdb command and capture its output
        """
        output = None
        tmp = os.popen("mktemp").read().strip()   #create temp file for capturing output
        gdb.execute("set logging enabled off") #prevent nested call
        gdb.execute("set height 0")
        gdb.execute(f"set logging file {tmp}")
        gdb.execute("set logging overwrite on")
        gdb.execute("set logging redirect on")
        gdb.execute("set logging enabled on")
        try:
            gdb.execute(command)
            gdb.flush()
            gdb.execute("set logging enabled off")
            with open(tmp, "r") as f:
                output = f.read()
        except Exception as e:
            gdb.execute("set logging enabled off")
            self.display(f"ERROR: {e}")
        os.remove(tmp) #delete temp file
        return output
    
    def decompile(self, function: str) -> str | None:
        """
        Returns a decompilation of `function` as a string
        """
        target = self._getTarget()
        if target is None:
            self.display(f"ERROR: No target is loaded")
            return None
        path = self.options["decomp_path"]
        if not self.decompiled:
            if os.path.exists(path):
                shutil.rmtree(path)
            os.mkdir(path)
            envVar = dict(os.environ, GHIDRA_INSTALL_DIR=os.path.expanduser(self.options["ghidra_path"]))
            self.display("Decompiling...")
            subprocess.run(["ghidrecomp", "-o", path, target], env=envVar, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.display("Done!")
            self.decompiled = True
        outDir = os.path.join(path, os.path.basename(target), function) + "*"
        functions = [filename for filename in glob.glob(outDir)]
        if len(functions) == 0:
            self.display(f"ERROR: No match for function with name `{function}`")
            return
        elif len(functions) > 1:
            self.display(f"ERROR: Multiple similar or duplicate functions found with name `{function}`")
            self.display(f"Specify with `decompile {{{', '.join([os.path.splitext(os.path.basename(filename))[0] for filename in functions])}}}`")
            return
        with open(functions[0], "r") as f:
            source = f.read()
        return source

    def _loadConfig(self, name="config.toml") -> dict:
        """
        Load default project options
        """
        options = dict()
        home = os.path.expanduser("~")
        configPath = os.path.join(home, "GDBDecompile", name)
        try:
            with open(configPath, "r") as f:
                options = toml.load(f)
        except toml.decoder.TomlDecodeError:
            self.display(f"ERROR: Cannot decode {configPath}. Exiting.")
        except FileNotFoundError:
            self.display(f"ERROR: Cannot locate {configPath}. Exiting.")
        except Exception as e:
            self.display(f"Error: {e}")
        self.loaded = True
        return options
    
    def _getTarget(self) -> str | None:
        """
        Get the path of the current target being analysed
        """
        target = self.executeCapture("info target")
        if target == "":
            return None
        return target.split("\n")[0].split('"')[1]
        
        
class GDBDecompileCommand(gdb.Command):
    """
    Wrapper of gdb.Command for custom "decompile" command
    """

    def __init__(self, name: str = "decompile"):
        self.name = name
        super(GDBDecompileCommand, self).__init__(self.name, gdb.COMMAND_DATA)

    def invoke(self, arg: str, from_tty: bool):
        if not Decompile.loaded:
            Decompile.display("ERROR: Extension improperly loaded. Exiting.")
            return
        args = arg.split(' ')
        self.dont_repeat()
        if len(args) > 1 or args[0] == "":
            Decompile.display("ERROR: Invalid command")
            Decompile.display("Usage: `decompile <function name>`")
            return
        code = Decompile.decompile(args[0])
        if code is not None:
            highlighted = highlight(code, CLexer(), Terminal256Formatter(style='github-dark'))
            print(highlighted)


def stringColour(message: str, hexCode: tuple) -> str:
    return f"\x1B[38;2;{hexCode[0]};{hexCode[1]};{hexCode[2]}m{message}\x1B[0m"

PROMPT_COLOUR = (255, 39, 38)

# Initialise global instances/variables

Decompile = GDBDecompile()

GDBDecompileCommand()
