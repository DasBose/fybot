#!/usr/bin/env python3
"""GUI launcher for configurable programs in the programs/ directory."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from loguru import logger

ROOT = Path(__file__).resolve().parent
PROGRAMS_DIR = ROOT / "programs"
LOGS_DIR = ROOT / "logs"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from io_test_panel import IOTestPanel  # noqa: E402
from program_elements.program import (  # noqa: E402
    BooleanParameter,
    EnumParameter,
    IntegerParameter,
    Program,
    RangeParameter,
    StringParameter,
)


def discover_programs(programs_dir: Path) -> dict[str, type[Program]]:
    """Load Program subclasses from Python files in programs_dir."""
    from program_elements.program import Program as ProgramBase

    discovered: dict[str, type[Program]] = {}
    if not programs_dir.is_dir():
        return discovered

    for path in sorted(programs_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"programs.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            print(f"Skipping {path.name}: {exc}", file=sys.stderr)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, ProgramBase)
                and obj is not ProgramBase
                and obj.__module__ == module_name
            ):
                discovered[obj.__name__] = obj

    return discovered


TOUCH_FONT_SIZE = 18
TOUCH_ROW_PADY = 10
TOUCH_COMBO_WIDTH = 24


class ProgramLauncher(tk.Tk):
    """Tkinter UI to select a :class:`Program`, edit its PARAMETERS, and run it in a background thread."""

    def __init__(self) -> None:
        super().__init__()
        self.title("FYBot Program Launcher")
        self.attributes("-zoomed", True)
        self.minsize(420, 480)
        self.bind("<Escape>", lambda _event: self.destroy())

        self.program_classes = discover_programs(PROGRAMS_DIR)
        self.program_instance: Program | None = None
        self.running_program: Program | None = None
        self.param_widgets: dict[str, dict[str, Any]] = {}
        self.run_thread: threading.Thread | None = None
        self._run_mode: str | None = None  # "run" | "io_test"
        self._log_sink_id: int | None = None
        self._touch_font = self._resolve_touch_font()
        self.io_panel: IOTestPanel | None = None

        self._setup_touch_styles()
        self._build_selector()
        self._build_parameters_area()
        self._build_actions()
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        if self.program_classes:
            first = next(iter(self.program_classes))
            self.program_var.set(first)
            self.load_program()
        else:
            self.status_var.set(f"No programs found in {PROGRAMS_DIR}")

    def _resolve_touch_font(self) -> tuple[str, int]:
        for family in ("DejaVu Sans", "Liberation Sans", "Sans"):
            if family in tkfont.families(self):
                return (family, TOUCH_FONT_SIZE)
        default = tkfont.nametofont("TkDefaultFont")
        return (default.cget("family"), TOUCH_FONT_SIZE)

    def _setup_touch_styles(self) -> None:
        style = ttk.Style(self)
        font = self._touch_font
        padding = (10, 14)
        style.configure("Touch.TLabel", font=font, padding=(0, 6))
        style.configure("Touch.TButton", font=font, padding=padding)
        style.configure("Touch.TCombobox", font=font, padding=(10, 12))
        style.configure("Touch.TSpinbox", font=font, padding=(8, 10))
        style.configure("Touch.TCheckbutton", font=font, padding=8)
        style.configure("Touch.TEntry", font=font, padding=(8, 10))

    def _create_combobox(self, parent: tk.Misc, **kwargs: Any) -> ttk.Combobox:
        widget = ttk.Combobox(parent, style="Touch.TCombobox", **kwargs)
        self._bind_touch_combobox(widget)
        return widget

    def _bind_touch_combobox(self, combobox: ttk.Combobox) -> None:
        def enlarge_popdown(_event: tk.Event | None = None) -> None:
            self.after(1, lambda: self._enlarge_combobox_popdown(combobox))

        combobox.bind("<Button-1>", enlarge_popdown, add="+")
        combobox.bind("<Down>", enlarge_popdown, add="+")
        combobox.bind("<space>", enlarge_popdown, add="+")

    def _enlarge_combobox_popdown(self, combobox: ttk.Combobox) -> None:
        try:
            popdown = combobox.tk.call("ttk::combobox::PopdownWindow", combobox)
            listbox = f"{popdown}.f.l"
            values = combobox.cget("values")
            row_count = max(4, min(len(values), 10))
            combobox.tk.call(
                listbox,
                "configure",
                "-font",
                self._touch_font,
                "-height",
                row_count,
            )
        except tk.TclError:
            pass

    def _build_selector(self) -> None:
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="Program", style="Touch.TLabel").pack(side="left")
        self.program_var = tk.StringVar()
        self.program_menu = self._create_combobox(
            frame,
            textvariable=self.program_var,
            values=sorted(self.program_classes),
            state="readonly",
            width=TOUCH_COMBO_WIDTH,
        )
        self.program_menu.pack(side="left", padx=(8, 8))
        self.program_menu.bind("<<ComboboxSelected>>", lambda _event: self.load_program())

        self.reload_button = ttk.Button(
            frame, text="Reload", command=self.reload_programs, style="Touch.TButton"
        )
        self.reload_button.pack(side="left")

    def _build_parameters_area(self) -> None:
        self.content_outer = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.content_outer.pack(fill="both", expand=True)

        self.params_section = ttk.Frame(self.content_outer)
        self.params_section.pack(fill="both", expand=True)

        ttk.Label(self.params_section, text="Parameters", style="Touch.TLabel").pack(
            anchor="w"
        )

        container = ttk.Frame(self.params_section)
        container.pack(fill="both", expand=True, pady=(4, 0))

        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.param_frame = ttk.Frame(self.canvas)

        self.param_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.param_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _scroll_canvas(event: tk.Event) -> None:
            if event.num == 5 or event.delta < 0:
                self.canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.canvas.yview_scroll(-1, "units")

        self.canvas.bind("<MouseWheel>", _scroll_canvas)
        self.canvas.bind("<Button-4>", _scroll_canvas)
        self.canvas.bind("<Button-5>", _scroll_canvas)

        self.io_section = ttk.Frame(self.content_outer)
        ttk.Label(self.io_section, text="IO Test", style="Touch.TLabel").pack(anchor="w")
        self.io_panel = IOTestPanel(
            self.io_section,
            label_style="Touch.TLabel",
            button_style="Touch.TButton",
            checkbutton_style="Touch.TCheckbutton",
            spinbox_style="Touch.TSpinbox",
            row_pady=TOUCH_ROW_PADY,
        )
        self.io_panel.pack(fill="both", expand=True, pady=(4, 0))

    def _build_actions(self) -> None:
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        self.run_button = ttk.Button(
            frame, text="Run", command=self.run_program, style="Touch.TButton"
        )
        self.run_button.pack(side="left")

        self.io_test_button = ttk.Button(
            frame, text="IO Test", command=self.run_io_test, style="Touch.TButton"
        )
        self.io_test_button.pack(side="left", padx=(8, 0))

        self.stop_button = ttk.Button(
            frame,
            text="Stop",
            command=self.stop_program,
            state="disabled",
            style="Touch.TButton",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status_var, style="Touch.TLabel").pack(
            side="left", padx=(12, 0)
        )

    def _show_params_view(self) -> None:
        self.io_section.pack_forget()
        if self.io_panel is not None:
            self.io_panel.detach()
        self.params_section.pack(fill="both", expand=True)

    def _show_io_test_view(self, program: Program) -> None:
        self.params_section.pack_forget()
        self.io_section.pack(fill="both", expand=True)
        if self.io_panel is not None:
            self.io_panel.attach(program)

    def _program_is_running(self) -> bool:
        return self.run_thread is not None and self.run_thread.is_alive()

    def _set_program_selection_locked(self, locked: bool) -> None:
        self.program_menu.configure(state="disabled" if locked else "readonly")
        self.reload_button.configure(state="disabled" if locked else "normal")

    def reload_programs(self) -> None:
        if self._program_is_running():
            messagebox.showwarning(
                "Program Running", "Stop the program before reloading programs."
            )
            return
        self.program_classes = discover_programs(PROGRAMS_DIR)
        names = sorted(self.program_classes)
        self.program_menu.configure(values=names)
        if names:
            if self.program_var.get() not in names:
                self.program_var.set(names[0])
            self.load_program()
            self.status_var.set("Programs reloaded")
        else:
            self.program_var.set("")
            self.clear_parameters()
            self.status_var.set(f"No programs found in {PROGRAMS_DIR}")

    def clear_parameters(self) -> None:
        for child in self.param_frame.winfo_children():
            child.destroy()
        self.param_widgets.clear()
        self.program_instance = None

    def load_program(self) -> None:
        if self._program_is_running():
            messagebox.showwarning(
                "Program Running", "Stop the program before switching programs."
            )
            return
        name = self.program_var.get()
        program_class = self.program_classes.get(name)
        if program_class is None:
            self.clear_parameters()
            return

        self.clear_parameters()

        try:
            self.program_instance = program_class()
        except Exception as exc:
            messagebox.showerror("Load Error", f"Could not instantiate {name}:\n{exc}")
            self.status_var.set("Load failed")
            return

        parameters = self.program_instance.PARAMETERS
        if not parameters:
            ttk.Label(
                self.param_frame,
                text="No configurable parameters.",
                style="Touch.TLabel",
            ).grid(row=0, column=0, sticky="w", pady=TOUCH_ROW_PADY)
        else:
            for row, (key, param) in enumerate(parameters.items()):
                self._add_parameter_row(row, key, param)

        self.status_var.set(f"Loaded {name}")

    def _add_parameter_row(self, row: int, key: str, param: Any) -> None:
        label = ttk.Label(
            self.param_frame, text=getattr(param, "name", key), style="Touch.TLabel"
        )
        label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=TOUCH_ROW_PADY)

        if isinstance(param, IntegerParameter):
            var = tk.IntVar(value=param.get_value())
            widget = ttk.Spinbox(
                self.param_frame,
                from_=param.min_value,
                to=param.max_value,
                textvariable=var,
                width=12,
                style="Touch.TSpinbox",
            )
            widget.grid(row=row, column=1, sticky="w", pady=TOUCH_ROW_PADY)
            self.param_widgets[key] = {"type": "int", "var": var}

        elif isinstance(param, BooleanParameter):
            var = tk.BooleanVar(value=param.get_value())
            widget = ttk.Checkbutton(
                self.param_frame, variable=var, style="Touch.TCheckbutton"
            )
            widget.grid(row=row, column=1, sticky="w", pady=TOUCH_ROW_PADY)
            self.param_widgets[key] = {"type": "bool", "var": var}

        elif isinstance(param, EnumParameter):
            var = tk.StringVar(value=param.get_value())
            values = sorted(param.values)
            widget = self._create_combobox(
                self.param_frame,
                textvariable=var,
                values=values,
                state="readonly",
                width=TOUCH_COMBO_WIDTH,
            )
            widget.grid(row=row, column=1, sticky="w", pady=TOUCH_ROW_PADY)
            self.param_widgets[key] = {"type": "enum", "var": var}
        
        elif isinstance(param, StringParameter):
            var = tk.StringVar(value=param.get_value())
            widget = ttk.Entry(
                self.param_frame,
                textvariable=var,
                width=TOUCH_COMBO_WIDTH,
                style="Touch.TEntry",
            )
            widget.grid(row=row, column=1, sticky="w", pady=TOUCH_ROW_PADY)
            self.param_widgets[key] = {"type": "string", "var": var}

        elif isinstance(param, RangeParameter):
            low, high = param.get_value()
            low_var = tk.IntVar(value=low)
            high_var = tk.IntVar(value=high)
            range_frame = ttk.Frame(self.param_frame)
            ttk.Spinbox(
                range_frame,
                from_=param.min_value,
                to=param.max_value,
                textvariable=low_var,
                width=6,
                style="Touch.TSpinbox",
            ).pack(side="left")
            ttk.Label(range_frame, text="to", style="Touch.TLabel").pack(
                side="left", padx=4
            )
            ttk.Spinbox(
                range_frame,
                from_=param.min_value,
                to=param.max_value,
                textvariable=high_var,
                width=6,
                style="Touch.TSpinbox",
            ).pack(side="left")
            range_frame.grid(row=row, column=1, sticky="w", pady=TOUCH_ROW_PADY)
            self.param_widgets[key] = {
                "type": "range",
                "low_var": low_var,
                "high_var": high_var,
            }

    def _apply_parameters(self) -> None:
        if self.program_instance is None:
            raise RuntimeError("No program loaded")

        for key, widgets in self.param_widgets.items():
            param_type = widgets["type"]
            if param_type == "int":
                value = widgets["var"].get()
            elif param_type == "bool":
                value = widgets["var"].get()
            elif param_type == "enum":
                value = widgets["var"].get()
            elif param_type == "string":
                value = widgets["var"].get()
            elif param_type == "range":
                value = (widgets["low_var"].get(), widgets["high_var"].get())
            else:
                continue
            self.program_instance.set_parameter(key, value)

    def _safe_log_stem(self, name: str) -> str:
        stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")
        return stem or "program"

    def _setup_run_logging(self, program: Program) -> Path:
        program_name = getattr(program, "NAME", None) or self.program_var.get()
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = LOGS_DIR / f"{timestamp}_{self._safe_log_stem(program_name)}.log"

        if self._log_sink_id is not None:
            logger.remove(self._log_sink_id)
            self._log_sink_id = None

        self._log_sink_id = logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            encoding="utf-8",
        )
        logger.info(f"Launcher: Logging to {log_file}")
        logger.info(f"Launcher: Running program {program.NAME} with parameters:") 
        for key, value in program.PARAMETERS.items():
            logger.info(f"Launcher: {key} = {value.get_value()}")
        return log_file

    def _teardown_run_logging(self) -> None:
        if self._log_sink_id is not None:
            logger.remove(self._log_sink_id)
            self._log_sink_id = None

    def _begin_program_thread(
        self, program: Program, mode: str, entry: Any, status_prefix: str
    ) -> None:
        log_file = self._setup_run_logging(program)
        self.running_program = program
        self._run_mode = mode
        self.run_button.configure(state="disabled")
        self.io_test_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._set_program_selection_locked(True)
        self.status_var.set(f"{status_prefix} ({log_file.name})")

        def target() -> None:
            try:
                entry()
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Program Error", str(e)))
            finally:
                self.after(0, self._on_program_finished)

        self.run_thread = threading.Thread(target=target, daemon=True)
        self.run_thread.start()

    def run_program(self) -> None:
        if self.program_instance is None:
            messagebox.showwarning("Run", "Select a program first.")
            return
        if self.run_thread is not None and self.run_thread.is_alive():
            messagebox.showwarning("Run", "A program is already running.")
            return

        try:
            self._apply_parameters()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid Parameters", str(exc))
            self.status_var.set("Invalid parameters")
            return

        program = self.program_instance
        self._show_params_view()
        self._begin_program_thread(program, "run", program.start, "Running...")

    def run_io_test(self) -> None:
        if self.program_instance is None:
            messagebox.showwarning("IO Test", "Select a program first.")
            return
        if self.run_thread is not None and self.run_thread.is_alive():
            messagebox.showwarning("IO Test", "A program is already running.")
            return

        try:
            self._apply_parameters()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid Parameters", str(exc))
            self.status_var.set("Invalid parameters")
            return

        program = self.program_instance
        self._show_io_test_view(program)
        self._begin_program_thread(
            program, "io_test", program.start_io_test, "IO Test..."
        )

    def stop_program(self) -> None:
        if self.running_program is None:
            return
        if self.run_thread is None or not self.run_thread.is_alive():
            return
        self.running_program.stop()
        logger.info("Launcher: Stop requested")
        self.status_var.set("Stopping...")

    def _on_window_close(self) -> None:
        if self.run_thread is not None and self.run_thread.is_alive():
            self.stop_program()
            self.run_thread.join(timeout=30.0)
            self.update()
            if self.run_thread is not None and self.run_thread.is_alive():
                logger.warning(
                    "Launcher: Timed out waiting for program to stop on window close"
                )
        if self.running_program is not None or self._log_sink_id is not None:
            self._on_program_finished()
        self.destroy()

    def _on_program_finished(self) -> None:
        logger.info("Launcher: Program finished")
        self._teardown_run_logging()
        was_io_test = self._run_mode == "io_test"
        self.running_program = None
        self.run_thread = None
        self._run_mode = None
        self.run_button.configure(state="normal")
        self.io_test_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self._set_program_selection_locked(False)
        if was_io_test:
            self._show_params_view()
        self.status_var.set("Finished")


def main() -> None:
    PROGRAMS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    app = ProgramLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()
