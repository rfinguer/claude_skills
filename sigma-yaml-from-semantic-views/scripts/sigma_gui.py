"""
Small native windows (tkinter, standard library) so the user never needs to open a terminal:
  * login()   -> Client ID / Client Secret typed in a window (secret masked). Values stay in memory only.
  * choose()  -> pick one row (workbook / connection) from a searchable list.
  * confirm() -> show the change summary (plus an optional red warning) and ask Publish/Apply / Cancel.
The windows are always on top so they are visible when Claude runs the CLI in the background.
"""
import tkinter as tk
from tkinter import ttk

TITLE = "Sigma - YAML push"


def _root():
    r = tk.Tk()
    r.title(TITLE)
    r.attributes("-topmost", True)
    r.resizable(True, True)
    r.after(200, lambda: (r.lift(), r.focus_force()))
    return r


def _center(r, w, h):
    r.update_idletasks()
    x = (r.winfo_screenwidth() - w) // 2
    y = (r.winfo_screenheight() - h) // 3
    r.geometry(f"{w}x{h}+{x}+{y}")


def login(host):
    """Return (client_id, client_secret) or (None, None) if cancelled."""
    out = {"id": None, "secret": None}
    r = _root()
    _center(r, 460, 230)
    f = ttk.Frame(r, padding=16)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text="Your own Sigma API credentials", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(f, text=f"Sent only to {host}. Nothing is saved.", foreground="#555").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
    ttk.Label(f, text="Client ID").grid(row=2, column=0, sticky="w")
    e_id = ttk.Entry(f, width=44, show="•")
    e_id.grid(row=2, column=1, pady=4)
    ttk.Label(f, text="Client Secret").grid(row=3, column=0, sticky="w")
    e_sec = ttk.Entry(f, width=44, show="•")
    e_sec.grid(row=3, column=1, pady=4)

    def ok(*_):
        out["id"], out["secret"] = e_id.get().strip(), e_sec.get().strip()
        e_id.delete(0, "end"); e_sec.delete(0, "end")
        r.destroy()

    b = ttk.Frame(f)
    b.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(b, text="Cancel", command=r.destroy).pack(side="right", padx=4)
    ttk.Button(b, text="Sign in", command=ok).pack(side="right")
    r.bind("<Return>", ok)
    r.bind("<Escape>", lambda *_: r.destroy())
    e_id.focus_set()
    r.mainloop()
    return out["id"], out["secret"]


def choose(title, rows, cols, key, note=""):
    """Searchable single-choice list. Returns rows[i][key] or None."""
    out = {"v": None}
    r = _root()
    _center(r, 820, 520)
    f = ttk.Frame(r, padding=12)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
    if note:
        ttk.Label(f, text=note, foreground="#555", wraplength=780).pack(anchor="w", pady=(2, 6))
    q = tk.StringVar()
    ttk.Entry(f, textvariable=q).pack(fill="x", pady=(0, 6))
    tv = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=260 if c != cols[0] else 300, anchor="w")
    sb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    tv.pack(side="left", fill="both", expand=True)
    sb.pack(side="left", fill="y")

    def fill(*_):
        tv.delete(*tv.get_children())
        t = q.get().lower()
        for i, row in enumerate(rows):
            vals = [str(row.get(c, "") or "") for c in cols]
            if not t or any(t in v.lower() for v in vals):
                tv.insert("", "end", iid=str(i), values=vals)

    def ok(*_):
        sel = tv.selection()
        if sel:
            out["v"] = rows[int(sel[0])].get(key)
            r.destroy()

    q.trace_add("write", fill)
    fill()
    tv.bind("<Double-1>", ok)
    b = ttk.Frame(r, padding=(12, 0, 12, 12))
    b.pack(fill="x")
    ttk.Button(b, text="Cancel", command=r.destroy).pack(side="right", padx=4)
    ttk.Button(b, text="Select", command=ok).pack(side="right")
    r.bind("<Return>", ok)
    r.bind("<Escape>", lambda *_: r.destroy())
    r.mainloop()
    return out["v"]


def confirm(title, text, warning=None, ok_label="Apply"):
    out = {"v": False}
    r = _root()
    _center(r, 640, 520 if warning else 420)
    f = ttk.Frame(r, padding=14)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
    if warning:
        tk.Label(f, text=warning, fg="#B00020", font=("Segoe UI", 10, "bold"), justify="left",
                 wraplength=600).pack(anchor="w", pady=(0, 8))
    t = tk.Text(f, height=14, wrap="word", font=("Consolas", 10))
    t.insert("1.0", text)
    t.configure(state="disabled")
    t.pack(fill="both", expand=True)

    def yes():
        out["v"] = True
        r.destroy()

    b = ttk.Frame(f)
    b.pack(fill="x", pady=(10, 0))
    ttk.Button(b, text="Cancel", command=r.destroy).pack(side="right", padx=4)
    ttk.Button(b, text=ok_label, command=yes).pack(side="right")
    r.bind("<Escape>", lambda *_: r.destroy())
    r.mainloop()
    return out["v"]
