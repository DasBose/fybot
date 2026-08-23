"""Shared Tkinter controls for Program IO Test mode."""

from __future__ import annotations

import tkinter as tk
from typing import Any
from tkinter import ttk

from program_elements.program import Program

POLL_MS = 150


class IOTestPanel(ttk.Frame):
    """On/off switches, level controls, and input state displays driven by a Program's IO config."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        label_style: str = "Touch.TLabel",
        button_style: str = "Touch.TButton",
        checkbutton_style: str = "Touch.TCheckbutton",
        spinbox_style: str = "Touch.TSpinbox",
        row_pady: int = 10,
    ) -> None:
        super().__init__(parent)
        self._label_style = label_style
        self._button_style = button_style
        self._checkbutton_style = checkbutton_style
        self._spinbox_style = spinbox_style
        self._row_pady = row_pady
        self._program: Program | None = None
        self._poll_after_id: str | None = None
        self._built = False
        self._input_vars: dict[str, tk.StringVar] = {}
        self._bool_vars: dict[str, tk.BooleanVar] = {}
        self._level_vars: dict[str, tk.IntVar] = {}
        self._status_var = tk.StringVar(value="Waiting for IO…")

        ttk.Label(self, textvariable=self._status_var, style=self._label_style).pack(
            anchor="w", pady=(0, 8)
        )
        self._body = ttk.Frame(self)
        self._body.pack(fill="both", expand=True)

    def attach(self, program: Program) -> None:
        self.detach()
        self._program = program
        self._status_var.set("Waiting for IO…")
        self._poll()

    def detach(self) -> None:
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
        self._program = None
        self._clear_body()
        self._built = False

    def _clear_body(self) -> None:
        for child in self._body.winfo_children():
            child.destroy()
        self._input_vars.clear()
        self._bool_vars.clear()
        self._level_vars.clear()

    def _poll(self) -> None:
        program = self._program
        if program is None:
            return

        if not self._built and program.io_ready.is_set():
            self._build_controls(program)
            self._built = True
            self._status_var.set("IO Test active")

        if self._built:
            self._refresh_inputs(program)

        self._poll_after_id = self.after(POLL_MS, self._poll)

    def _build_controls(self, program: Program) -> None:
        self._clear_body()
        row = 0

        if program.boolean_outputs:
            ttk.Label(
                self._body, text="Boolean outputs", style=self._label_style
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
            row += 1
            for key, output in program.boolean_outputs.items():
                row = self._add_boolean_row(row, key, output)
            row += 1

        if program.variable_outputs:
            ttk.Label(
                self._body, text="Variable outputs", style=self._label_style
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
            row += 1
            for key, output in program.variable_outputs.items():
                row = self._add_variable_row(row, key, output)
            row += 1

        if program.inputs:
            ttk.Label(self._body, text="Inputs", style=self._label_style).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(8, 4)
            )
            row += 1
            for key, inp in program.inputs.items():
                row = self._add_input_row(row, key, inp)

        if not (
            program.boolean_outputs or program.variable_outputs or program.inputs
        ):
            ttk.Label(
                self._body,
                text="No IO channels configured for this program.",
                style=self._label_style,
            ).grid(row=0, column=0, sticky="w")

    def _add_boolean_row(self, row: int, key: str, output: Any) -> int:
        ttk.Label(self._body, text=output.name, style=self._label_style).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=self._row_pady
        )
        var = tk.BooleanVar(value=output.get_value())
        self._bool_vars[key] = var

        def on_toggle(*_args: object, k: str = key, v: tk.BooleanVar = var) -> None:
            program = self._program
            if program is None or k not in program.boolean_outputs:
                return
            try:
                program.boolean_outputs[k].set_value(v.get())
            except Exception as exc:
                self._status_var.set(f"Output error: {exc}")

        widget = ttk.Checkbutton(
            self._body,
            text="On",
            variable=var,
            style=self._checkbutton_style,
            command=on_toggle,
        )
        widget.grid(row=row, column=1, sticky="w", pady=self._row_pady)
        return row + 1

    def _add_variable_row(self, row: int, key: str, output: Any) -> int:
        ttk.Label(self._body, text=output.name, style=self._label_style).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=self._row_pady
        )
        var = tk.IntVar(value=output.get_value())
        self._level_vars[key] = var

        def apply_level(k: str = key, v: tk.IntVar = var) -> None:
            program = self._program
            if program is None or k not in program.variable_outputs:
                return
            try:
                program.variable_outputs[k].set_value(int(v.get()))
            except (ValueError, tk.TclError) as exc:
                self._status_var.set(f"Output error: {exc}")

        controls = ttk.Frame(self._body)
        spin = ttk.Spinbox(
            controls,
            from_=output.min_value,
            to=output.max_value,
            textvariable=var,
            width=8,
            style=self._spinbox_style,
            command=apply_level,
        )
        spin.pack(side="left")
        spin.bind("<Return>", lambda _e: apply_level())
        spin.bind("<FocusOut>", lambda _e: apply_level())
        ttk.Button(
            controls,
            text="Set",
            style=self._button_style,
            command=apply_level,
        ).pack(side="left", padx=(8, 0))
        controls.grid(row=row, column=1, sticky="w", pady=self._row_pady)
        return row + 1

    def _add_input_row(self, row: int, key: str, inp: Any) -> int:
        ttk.Label(self._body, text=inp.name, style=self._label_style).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=self._row_pady
        )
        var = tk.StringVar(value="Off")
        self._input_vars[key] = var
        ttk.Label(self._body, textvariable=var, style=self._label_style).grid(
            row=row, column=1, sticky="w", pady=self._row_pady
        )
        return row + 1

    def _refresh_inputs(self, program: Program) -> None:
        for key, var in self._input_vars.items():
            inp = program.inputs.get(key)
            if inp is None:
                continue
            try:
                var.set("On" if inp.get_value() else "Off")
            except Exception:
                var.set("Error")
