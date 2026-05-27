import contextlib
import queue
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pipeline_core as core


APP_TITLE = "Pipeline Solar v10"
COLORS = {
    "bg": "#eef3f8",
    "surface": "#ffffff",
    "surface_alt": "#f7fafc",
    "border": "#d8e0e8",
    "text": "#12202f",
    "muted": "#5c6b7a",
    "primary": "#0f6b5f",
    "primary_dark": "#0a4d44",
    "blue": "#1f5f99",
    "log_bg": "#0b1220",
    "log_fg": "#d9e6f2",
}


class QueueWriter:
    def __init__(self, out_queue):
        self.out_queue = out_queue

    def write(self, text):
        if text:
            self.out_queue.put(("log", text))

    def flush(self):
        pass


class PipelineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1160x740")
        self.minsize(1040, 640)
        self.queue = queue.Queue()
        self.running = False
        self.pdfs = []
        self.planilhas = []

        self._setup_style()
        self._build_ui()
        self._load_initial_state()
        self.after(120, self._drain_queue)

    def _setup_style(self):
        self.configure(bg=COLORS["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["surface"])
        style.configure("Header.TFrame", background=COLORS["primary"])
        style.configure("MetricBox.TFrame", background=COLORS["surface_alt"])

        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=COLORS["primary"], foreground="#ffffff", font=("Segoe UI", 20, "bold"))
        style.configure("HeaderSub.TLabel", background=COLORS["primary"], foreground="#d8f2ed", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI", 11, "bold"))
        style.configure("Metric.TLabel", background=COLORS["surface_alt"], foreground=COLORS["text"], font=("Segoe UI", 18, "bold"))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("MutedAlt.TLabel", background=COLORS["surface_alt"], foreground=COLORS["muted"], font=("Segoe UI", 9))

        style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.map(
            "Accent.TButton",
            foreground=[("!disabled", "#ffffff")],
            background=[("!disabled", COLORS["primary"]), ("active", COLORS["primary_dark"])],
        )

        style.configure("TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", COLORS["surface"])], foreground=[("active", COLORS["text"])])
        style.configure("Horizontal.TProgressbar", troughcolor=COLORS["border"], background=COLORS["primary"])

    def _build_ui(self):
        root = ttk.Frame(self, padding=0)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Header.TFrame", padding=(22, 16))
        header.pack(fill="x")

        title_box = ttk.Frame(header, style="Header.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text=APP_TITLE, style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Importacao, diagnostico e geracao de XLSX em um fluxo unico",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        ttk.Button(header, text="Atualizar", command=self.refresh_all).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Abrir saida", command=self.open_output_folder).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Abrir cliente", command=self.open_client_folder).pack(side="right")

        main = ttk.Frame(root, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Panel.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 14))

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(left, text="Operacao", style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text="Cliente", style="Panel.TLabel").pack(anchor="w", pady=(14, 0))
        self.cliente_var = tk.StringVar()
        self.cliente_combo = ttk.Combobox(left, textvariable=self.cliente_var, width=34)
        self.cliente_combo.pack(fill="x", pady=(6, 12))

        ttk.Label(left, text="Downloads", style="Panel.TLabel").pack(anchor="w")
        dl_row = ttk.Frame(left, style="Panel.TFrame")
        dl_row.pack(fill="x", pady=(6, 12))
        self.downloads_var = tk.StringVar(value=str(core.DOWNLOADS_PADRAO))
        ttk.Entry(dl_row, textvariable=self.downloads_var, width=28).pack(side="left", fill="x", expand=True)
        ttk.Button(dl_row, text="...", width=3, command=self.choose_downloads).pack(side="left", padx=(6, 0))

        ttk.Label(left, text="Janela de busca", style="Panel.TLabel").pack(anchor="w")
        self.dias_var = tk.IntVar(value=7)
        ttk.Spinbox(left, from_=1, to=60, textvariable=self.dias_var, width=8).pack(anchor="w", pady=(6, 12))

        self.importar_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Importar Downloads", variable=self.importar_var).pack(anchor="w", pady=(0, 8))
        self.quarentena_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Mover origem para quarentena", variable=self.quarentena_var).pack(anchor="w", pady=(0, 16))

        ttk.Button(left, text="Previa dos Downloads", command=self.preview_downloads).pack(fill="x", pady=(0, 8))
        self.run_button = ttk.Button(left, text="Importar e Processar", style="Accent.TButton", command=self.run_pipeline)
        self.run_button.pack(fill="x", pady=(0, 14))

        metrics = ttk.Frame(left, style="Panel.TFrame")
        metrics.pack(fill="x", pady=(10, 16))
        self.pdf_count = tk.StringVar(value="0")
        self.xls_count = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="Pronto")
        self._metric(metrics, "PDFs", self.pdf_count)
        self._metric(metrics, "Planilhas", self.xls_count)
        ttk.Label(metrics, textvariable=self.status_var, style="Muted.TLabel", wraplength=260).pack(anchor="w", pady=(10, 0))

        info = ttk.Frame(left, style="Panel.TFrame")
        info.pack(fill="x", pady=(8, 0))
        ttk.Label(info, text="Saida", style="Section.TLabel").pack(anchor="w")
        ttk.Label(info, text=str(Path.home() / "Desktop" / "Analise Energia"), style="Muted.TLabel", wraplength=260).pack(anchor="w", pady=(6, 0))

        preview_panel = ttk.Frame(right, style="Panel.TFrame", padding=14)
        preview_panel.grid(row=0, column=0, sticky="ew")
        preview_panel.columnconfigure(0, weight=1)
        preview_panel.columnconfigure(1, weight=1)
        ttk.Label(preview_panel, text="Faturas encontradas", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(preview_panel, text="Geracao encontrada", style="Section.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.pdf_list = self._make_listbox(preview_panel)
        self.xls_list = self._make_listbox(preview_panel)
        self.pdf_list.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.xls_list.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))

        log_panel = ttk.Frame(right, style="Panel.TFrame", padding=14)
        log_panel.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        log_panel.rowconfigure(1, weight=1)
        log_panel.columnconfigure(0, weight=1)
        ttk.Label(log_panel, text="Execucao", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.log_text = tk.Text(
            log_panel,
            bg=COLORS["log_bg"],
            fg=COLORS["log_fg"],
            insertbackground="#ffffff",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            padx=10,
            pady=10,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        scroll = ttk.Scrollbar(log_panel, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(8, 0))
        self.log_text.configure(yscrollcommand=scroll.set)

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", padx=18, pady=(0, 16))

    def _make_listbox(self, parent):
        return tk.Listbox(
            parent,
            height=8,
            bg="#ffffff",
            fg=COLORS["text"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            relief="flat",
            selectbackground=COLORS["blue"],
            selectforeground="#ffffff",
            activestyle="none",
            font=("Segoe UI", 9),
        )

    def _metric(self, parent, label, var):
        box = ttk.Frame(parent, style="MetricBox.TFrame", padding=(10, 8))
        box.pack(fill="x", pady=(0, 8))
        ttk.Label(box, textvariable=var, style="Metric.TLabel").pack(side="left")
        ttk.Label(box, text=label, style="MutedAlt.TLabel").pack(side="left", padx=(8, 0))

    def _load_initial_state(self):
        self.refresh_clients()
        self.preview_downloads()

    def refresh_all(self):
        self.refresh_clients()
        self.preview_downloads()

    def refresh_clients(self):
        try:
            clientes = core.listar_clientes("")
        except Exception:
            clientes = []
        self.cliente_combo["values"] = clientes

    def choose_downloads(self):
        selected = filedialog.askdirectory(initialdir=self.downloads_var.get() or str(Path.home()))
        if selected:
            self.downloads_var.set(selected)
            self.preview_downloads()

    def preview_downloads(self):
        origem = Path(self.downloads_var.get()).expanduser()
        try:
            self.pdfs, self.planilhas = core._coletar_baixados(origem, int(self.dias_var.get()))
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Nao foi possivel ler Downloads:\n{exc}")
            self.pdfs, self.planilhas = [], []

        self.pdf_list.delete(0, "end")
        self.xls_list.delete(0, "end")
        for item in self.pdfs:
            self.pdf_list.insert("end", item.name)
        for item in self.planilhas:
            self.xls_list.insert("end", item.name)
        self.pdf_count.set(str(len(self.pdfs)))
        self.xls_count.set(str(len(self.planilhas)))
        self.status_var.set("Previa atualizada")

    def run_pipeline(self):
        if self.running:
            return
        cliente = self.cliente_var.get().strip()
        if not cliente:
            messagebox.showwarning(APP_TITLE, "Informe o nome do cliente.")
            return
        self.running = True
        self.run_button.configure(state="disabled")
        self.progress.start(10)
        self.log_text.delete("1.0", "end")
        self.status_var.set("Executando")
        args = {
            "cliente": cliente,
            "downloads": Path(self.downloads_var.get()).expanduser(),
            "dias": int(self.dias_var.get()),
            "importar": self.importar_var.get(),
            "quarentena": self.quarentena_var.get(),
        }
        threading.Thread(target=self._worker, args=(args,), daemon=True).start()

    def _worker(self, args):
        writer = QueueWriter(self.queue)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                out = self._execute_pipeline(**args)
            self.queue.put(("done", out))
        except Exception as exc:
            self.queue.put(("error", str(exc)))

    def _execute_pipeline(self, cliente, downloads, dias, importar, quarentena):
        print("=" * 60)
        print(f"{APP_TITLE} - {cliente}")
        print("=" * 60)

        pasta_cliente, pdf_dir, xlsx_dir, cliente_ja_existia = core.preparar_pasta_cliente(cliente)
        print(f"Cliente: {cliente}")
        print(f"Pasta: {'existente' if cliente_ja_existia else 'criada agora'}")
        print(f"Base: {core.BASE_DIR}")

        if importar:
            self._import_files(cliente, pasta_cliente, downloads, dias, quarentena)

        pdf_paths, origem_pdfs = core.coletar_com_fallback(pasta_cliente, pdf_dir, (".pdf",))
        xlsx_paths, origem_xlsx = core.coletar_com_fallback(pasta_cliente, xlsx_dir, (".xlsx", ".xls"))
        print(f"PDFs encontrados: {len(pdf_paths)} | {origem_pdfs}")
        print(f"XLS/XLSX encontrados: {len(xlsx_paths)} | {origem_xlsx}")

        if not pdf_paths and not xlsx_paths:
            raise RuntimeError("Nenhum arquivo encontrado para processar.")

        print("\n[1/3] Extraindo faturas PDF...")
        faturas = core.extrair_faturas(pdf_paths) if pdf_paths else []

        print("\n[2/3] Consolidando relatorios de geracao...")
        if xlsx_paths:
            geracao_diaria, detalhes_geracao = core.extrair_geracao(xlsx_paths, retornar_detalhes=True)
        else:
            geracao_diaria, detalhes_geracao = [], []

        core.diagnosticar_conjunto(pdf_paths, xlsx_paths, faturas, detalhes_geracao)

        print("\n[3/3] Salvando XLSX...")
        pasta_out = Path.home() / "Desktop" / "Analise Energia"
        pasta_out.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out = pasta_out / f"Dados IA - {cliente} - {ts}.xlsx"
        core.salvar_xlsx(faturas, geracao_diaria, out, cliente)

        total_kwh = sum(r["kwh"] for r in geracao_diaria)
        print("=" * 60)
        print(f"Arquivo: {out}")
        print(f"Faturas: {len(faturas)} meses")
        print(f"Geracao: {len(geracao_diaria)} dias | {round(total_kwh, 1)} kWh total")
        print("=" * 60)
        return out

    def _import_files(self, cliente, pasta_cliente, downloads, dias, quarentena):
        pdfs, planilhas = core._coletar_baixados(downloads, dias)
        print("\n[0/3] Importando Downloads...")
        print(f"Origem: {downloads}")
        print(f"PDFs na previa: {len(pdfs)}")
        print(f"Planilhas na previa: {len(planilhas)}")
        if not pdfs and not planilhas:
            print("Nenhum arquivo recente para importar.")
            return

        if quarentena:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            quarentena_dir = downloads / core.QUARENTENA_IMPORTADOS / cliente / ts
            qtd_pdfs, mov_pdfs = core._copiar_para_pasta(pdfs, pasta_cliente / "Contas", "fatura", quarentena_dir)
            qtd_xls, mov_xls = core._copiar_para_pasta(planilhas, pasta_cliente / "Dados", "geracao", quarentena_dir)
            print(f"PDFs copiados: {qtd_pdfs}")
            print(f"Planilhas copiadas: {qtd_xls}")
            print(f"Originais em quarentena: {mov_pdfs + mov_xls}")
        else:
            qtd_pdfs = self._copy_only(pdfs, pasta_cliente / "Contas")
            qtd_xls = self._copy_only(planilhas, pasta_cliente / "Dados")
            print(f"PDFs copiados: {qtd_pdfs}")
            print(f"Planilhas copiadas: {qtd_xls}")
            print("Originais preservados na origem.")

    def _copy_only(self, arquivos, destino_dir):
        import shutil

        destino_dir.mkdir(parents=True, exist_ok=True)
        total = 0
        for origem in arquivos:
            destino = core._nome_livre(destino_dir / origem.name)
            shutil.copy2(origem, destino)
            print(f"  {origem.name} -> {destino_dir.name}")
            total += 1
        return total

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.log_text.insert("end", payload)
                    self.log_text.see("end")
                elif kind == "done":
                    self.running = False
                    self.progress.stop()
                    self.run_button.configure(state="normal")
                    self.status_var.set("Concluido")
                    self.refresh_clients()
                    messagebox.showinfo(APP_TITLE, f"Arquivo gerado:\n{payload}")
                elif kind == "error":
                    self.running = False
                    self.progress.stop()
                    self.run_button.configure(state="normal")
                    self.status_var.set("Erro")
                    messagebox.showerror(APP_TITLE, payload)
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def open_output_folder(self):
        self._open_path(Path.home() / "Desktop" / "Analise Energia")

    def open_client_folder(self):
        cliente = self.cliente_var.get().strip()
        if not cliente:
            messagebox.showwarning(APP_TITLE, "Informe o nome do cliente.")
            return
        self._open_path(core.BASE_DIR / cliente)

    def _open_path(self, path):
        path = Path(path)
        if not path.exists():
            messagebox.showwarning(APP_TITLE, f"Caminho nao encontrado:\n{path}")
            return
        subprocess.Popen(["explorer", str(path)])


if __name__ == "__main__":
    PipelineApp().mainloop()
