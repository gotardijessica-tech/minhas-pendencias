# Minhas Pendências — janela simples com duas listas:
#   1. "Do Flow": atividades em que você é a responsável no app de Atas. SÓ
#      LEITURA — este app nunca muda nada no Flow. Duas fontes possíveis
#      (config.json → "fonte"):
#        "arquivo": lê o dados.json direto (o PC da editora, que tem o arquivo);
#        "site":    baixa do site publicado, entrando com o SEU login do
#                   Cloudflare Access (via cloudflared). Para quem não tem o
#                   dados.json. Guarda a última versão em cache_flow.json, então
#                   abre na hora e funciona sem internet.
#      Na primeira vez o app escolhe sozinho: se o dados.json existe, "arquivo";
#      senão, "site".
#   2. "Minhas": pendências avulsas que você digita aqui. Ficam em
#      minhas_pendencias.json, nesta mesma pasta.
#
# Como abrir:
#   pythonw pendencias.pyw          → abre sempre (atalho da área de trabalho)
#   pythonw pendencias.pyw --auto   → abre só se ainda não abriu hoje
#                                     (é o que a Tarefa Agendada chama ao ligar
#                                     o PC e ao voltar da suspensão)

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
from datetime import date, datetime
from tkinter import messagebox, ttk

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_CONFIG = os.path.join(PASTA, "config.json")
ARQ_MINHAS = os.path.join(PASTA, "minhas_pendencias.json")
ARQ_ESTADO = os.path.join(PASTA, "estado.json")
ARQ_CACHE = os.path.join(PASTA, "cache_flow.json")

CONFIG_PADRAO = {
    # Vazio = descobrir sozinho pelo e-mail do login (só no modo "site").
    "meuNome": "",
    "dadosFlow": os.path.join(os.path.expanduser("~"), "Documents", "AtasApp", "dados.json"),
    "siteFlow": "https://flow.akisen-pdi.workers.dev",
}

# No modo "site", de quanto em quanto tempo baixar de novo enquanto a janela
# está aberta.
MINUTOS_ENTRE_DOWNLOADS = 30

# Porta usada só para garantir UMA janela aberta: se o app já está aberto, a
# segunda cópia avisa a primeira ("mostre-se") e fecha.
PORTA_UNICA = 47831

# Versão deste arquivo. AO MUDAR O APP, SUBA ESTE NÚMERO antes de publicar no
# GitHub: é comparando com ele que os outros PCs descobrem que há novidade.
VERSAO = "1.2"

# De onde os outros PCs baixam as versões novas (repositório público).
REPO_RAW = "https://raw.githubusercontent.com/gotardijessica-tech/minhas-pendencias/main/"
ARQUIVOS_DO_APP = ["pendencias.pyw", "instalar.ps1", "README.md"]

PRIORIDADE_ORDEM = {"alta": 0, "media": 1, "baixa": 2}
PRIORIDADE_TEXTO = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ================= ARQUIVOS =================

def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def gravar_json(caminho, dados):
    # Grava num arquivo temporário e troca de uma vez: se o PC desligar no
    # meio, o arquivo antigo continua inteiro.
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


def carregar_config():
    config = ler_json(ARQ_CONFIG, None) or {}
    mudou = not os.path.exists(ARQ_CONFIG)
    for chave, valor in CONFIG_PADRAO.items():
        if chave not in config:
            config[chave] = valor
            mudou = True
    if config.get("fonte") not in ("arquivo", "site"):
        config["fonte"] = "arquivo" if os.path.exists(config["dadosFlow"]) else "site"
        mudou = True
    if mudou:
        gravar_json(ARQ_CONFIG, config)
    return config


# ================= ESTADO INTERNO (estado.json) =================
# O que o app precisa lembrar entre uma abertura e outra:
#   ultimoDia          → último dia em que a lista apareceu sozinha
#   instaladorAplicado → "impressão digital" do instalar.ps1 que já rodou

def ler_estado():
    return ler_json(ARQ_ESTADO, {})


def gravar_estado(chave, valor):
    # Muda só uma chave e mantém as outras.
    estado = ler_estado()
    estado[chave] = valor
    gravar_json(ARQ_ESTADO, estado)


# ================= "PRIMEIRA VEZ NO DIA" =================

def ja_abriu_hoje():
    return ler_estado().get("ultimoDia") == date.today().isoformat()


def marcar_aberto_hoje():
    gravar_estado("ultimoDia", date.today().isoformat())


# ================= FONTE "ARQUIVO" =================

def dados_do_arquivo(config):
    """Devolve os dados do Flow lidos do dados.json. Erro → RuntimeError."""
    caminho = config["dadosFlow"]
    # O app de Atas guarda cópias de segurança; se o principal estiver
    # ilegível (por ex. o Drive sincronizando), tenta a cópia.
    for tentativa in [caminho, caminho.replace("dados.json", "dados.bak1.json")]:
        dados = ler_json(tentativa, None)
        if dados is not None:
            return dados
    raise RuntimeError(f"Não consegui ler o arquivo do Flow:\n{caminho}")


# ================= FONTE "SITE" =================
#
# O site fica atrás do Cloudflare Access. O cloudflared (programa oficial da
# Cloudflare) faz o login: abre o navegador na primeira vez, você entra com o
# seu e-mail, e ele guarda um "passe" (token) no seu PC. Com esse passe no
# cabeçalho cf-access-token, o site responde como se fosse o seu navegador.
# Quando o passe vence, o navegador abre de novo para você entrar.

class PrecisaLogin(Exception):
    pass


def achar_cloudflared():
    caminho = shutil.which("cloudflared")
    if caminho:
        return caminho
    # O app pode ter sido aberto com um PATH antigo (de antes da instalação):
    # lê o PATH atual direto do registro do Windows.
    import winreg
    pastas_path = []
    for raiz, chave in [(winreg.HKEY_CURRENT_USER, r"Environment"),
                        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")]:
        try:
            with winreg.OpenKey(raiz, chave) as k:
                pastas_path.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    caminho = shutil.which("cloudflared", path=os.pathsep.join(pastas_path))
    if caminho:
        return caminho
    # Recém-instalado pelo winget, o PATH desta sessão ainda não o conhece.
    for pasta in [os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links")]:
        candidato = os.path.join(pasta, "cloudflared", "cloudflared.exe")
        if os.path.exists(candidato):
            return candidato
        candidato = os.path.join(pasta, "cloudflared.exe")
        if os.path.exists(candidato):
            return candidato
    raise RuntimeError("O cloudflared não está instalado. Rode o instalar.ps1 de novo.")


def rodar_cloudflared(argumentos, tempo_max):
    # CREATE_NO_WINDOW: não pisca janela preta de terminal.
    return subprocess.run([achar_cloudflared(), *argumentos], capture_output=True, text=True,
                          timeout=tempo_max, creationflags=subprocess.CREATE_NO_WINDOW)


def token_do_access(site, pode_abrir_login):
    r = rodar_cloudflared(["access", "token", f"-app={site}"], tempo_max=30)
    token = r.stdout.strip()
    if r.returncode == 0 and token.count(".") == 2:
        return token
    if not pode_abrir_login:
        raise PrecisaLogin()
    # Abre o navegador e espera você terminar o login (até 5 minutos).
    rodar_cloudflared(["access", "login", site], tempo_max=300)
    r = rodar_cloudflared(["access", "token", f"-app={site}"], tempo_max=30)
    token = r.stdout.strip()
    if r.returncode == 0 and token.count(".") == 2:
        return token
    raise RuntimeError("O login no Cloudflare não foi concluído.")


class NaoSeguirRedirecionamento(urllib.request.HTTPRedirectHandler):
    # Se o Access não aceitar o passe, ele redireciona para a tela de login.
    # Não seguimos: um redirecionamento aqui quer dizer "precisa entrar de novo".
    def redirect_request(self, *args, **kwargs):
        return None


def baixar(url, token):
    abridor = urllib.request.build_opener(NaoSeguirRedirecionamento)
    # User-Agent próprio: o Cloudflare BLOQUEIA (erro 1010) o nome padrão do
    # Python ("Python-urllib"), antes mesmo de olhar o login.
    pedido = urllib.request.Request(url, headers={
        "cf-access-token": token,
        "User-Agent": "MinhasPendencias/1.0 (Windows)",
    })
    try:
        with abridor.open(pedido, timeout=20) as resposta:
            return resposta.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # O Access recusa um passe vencido/inválido redirecionando para a tela
        # de login. Um 403 é OUTRA coisa (bloqueio do Cloudflare): não adianta
        # pedir login de novo, então mostramos o erro como ele é.
        if e.code in (301, 302, 303, 307, 308, 401):
            raise PrecisaLogin()
        detalhe = e.read()[:80].decode("utf-8", "replace").strip()
        raise RuntimeError(f"O site respondeu com erro {e.code}. {detalhe}")


def extrair_estado(html):
    # O site é uma página só, com os dados colados dentro dela assim:
    #   <script>window.__ESTADO__ = {...};</script>
    marca = "window.__ESTADO__ = "
    inicio = html.find(marca)
    if inicio < 0:
        raise PrecisaLogin()  # veio outra página (a de login, por exemplo)
    dados, _ = json.JSONDecoder().raw_decode(html, inicio + len(marca))
    return dados


def dados_do_site(config, pode_abrir_login):
    """Baixa os dados publicados e o e-mail de quem entrou."""
    site = config["siteFlow"].rstrip("/")
    for tentativa in range(2):
        token = token_do_access(site, pode_abrir_login)
        try:
            dados = extrair_estado(baixar(site + "/", token))
            try:
                email = json.loads(baixar(site + "/api/eu", token)).get("email", "")
            except (PrecisaLogin, RuntimeError, ValueError, OSError):
                email = ""
            return dados, email
        except PrecisaLogin:
            # Passe vencido ou recusado: pede um novo (uma vez só).
            if tentativa == 0 and pode_abrir_login:
                rodar_cloudflared(["access", "login", site], tempo_max=300)
                continue
            raise


def nome_pelo_email(dados, email):
    email = (email or "").strip().lower()
    if not email:
        return ""
    for p in dados.get("pessoas", []):
        if str(p.get("email", "")).strip().lower() == email:
            return p.get("nome", "")
    return ""


# ================= ATUALIZAÇÃO PELO GITHUB =================
#
# Ao abrir, o app baixa o pendencias.pyw publicado no GitHub e compara o
# VERSAO de lá com o daqui. Se o de lá for maior, mostra uma faixa com o botão
# "Atualizar agora". Na pasta da editora (que é o próprio repositório git) nada
# disso roda: lá as mudanças vêm do git, e o app não pode sobrescrever o
# arquivo que está sendo editado.

def eh_pasta_do_git():
    return os.path.isdir(os.path.join(PASTA, ".git"))


def baixar_do_repo(nome_arquivo):
    pedido = urllib.request.Request(REPO_RAW + nome_arquivo,
                                    headers={"User-Agent": "MinhasPendencias/" + VERSAO})
    with urllib.request.urlopen(pedido, timeout=15) as resposta:
        return resposta.read()


def versao_do_codigo(codigo):
    """Acha a linha VERSAO = "x.y" dentro do código. Não achou → None."""
    for linha in codigo.splitlines():
        if linha.startswith("VERSAO = "):
            return linha.split("=", 1)[1].strip().strip('"')
    return None


def versao_maior(a, b):
    """'1.10' > '1.9'? Compara número por número."""
    try:
        return tuple(int(x) for x in a.split(".")) > tuple(int(x) for x in b.split("."))
    except ValueError:
        return False


def versao_nova_disponivel():
    """Devolve o número da versão nova, ou None (sem novidade ou sem internet)."""
    if eh_pasta_do_git():
        return None
    try:
        codigo = baixar_do_repo("pendencias.pyw").decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    nova = versao_do_codigo(codigo)
    if nova and versao_maior(nova, VERSAO):
        return nova
    return None


def instalar_versao_nova():
    """Baixa os arquivos do app e troca os daqui. Erro → exceção, nada trocado."""
    baixados = {}
    for nome in ARQUIVOS_DO_APP:
        baixados[nome] = baixar_do_repo(nome)
    # Confere ANTES de trocar que o código novo veio inteiro: tem o número da
    # versão, chega até a última linha do app (um download cortado pela
    # metade pode até ser Python válido) e é Python válido.
    codigo = baixados["pendencias.pyw"].decode("utf-8")
    if not versao_do_codigo(codigo) or 'if __name__ == "__main__":' not in codigo:
        raise RuntimeError("o arquivo baixado veio incompleto")
    compile(codigo, "pendencias.pyw", "exec")

    # Guarda a versão atual como .bak, caso seja preciso voltar atrás.
    atual = os.path.join(PASTA, "pendencias.pyw")
    shutil.copyfile(atual, atual + ".bak")
    for nome, conteudo in baixados.items():
        destino = os.path.join(PASTA, nome)
        with open(destino + ".tmp", "wb") as f:
            f.write(conteudo)
        os.replace(destino + ".tmp", destino)


def aplicar_instalador_se_mudou():
    """No PC dos colegas: se o instalar.ps1 mudou (veio numa atualização), roda
    ele de novo, escondido, para a tarefa diária e os atalhos ficarem iguais
    aos da versão nova. Na pasta do git não roda: lá a editora roda o
    instalador quando quiser."""
    if eh_pasta_do_git():
        return
    instalador = os.path.join(PASTA, "instalar.ps1")
    try:
        with open(instalador, "rb") as f:
            impressao = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return
    if ler_estado().get("instaladorAplicado") == impressao:
        return  # esta versão do instalador já rodou
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                              "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    try:
        r = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", instalador],
                           capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return  # tenta de novo na próxima vez que o app abrir
    if r.returncode == 0:
        gravar_estado("instaladorAplicado", impressao)


# ================= PENDÊNCIAS DO FLOW =================

def proxima_reuniao(reunioes, projeto_id, hoje_iso):
    # Mesma regra do app de Atas (server/agenda.js): a reunião 'agendada' do
    # projeto com data ESTRITAMENTE depois de hoje, a mais próxima.
    melhor = None
    for r in reunioes:
        if r.get("projetoId") != projeto_id or r.get("status") != "agendada":
            continue
        if not r.get("data", "") > hoje_iso:
            continue
        if melhor is None or r["data"] < melhor:
            melhor = r["data"]
    return melhor


def pendencias_da_pessoa(dados, nome):
    hoje_iso = date.today().isoformat()
    projetos = {p["id"]: p.get("nome", "") for p in dados.get("projetos", [])}
    reunioes = dados.get("reunioes", [])
    nome = nome.strip().lower()

    lista = []
    for p in dados.get("pendencias", []):
        if p.get("status") != "aFazer":
            continue
        if str(p.get("responsavel", "")).strip().lower() != nome:
            continue
        if p.get("prazoTipo") == "dataFixa":
            prazo = p.get("prazoData")
            prazo_obs = ""
        else:
            prazo = proxima_reuniao(reunioes, p.get("projetoId"), hoje_iso)
            prazo_obs = "próx. reunião" if prazo else "sem reunião agendada"
        lista.append({
            "texto": p.get("acao", ""),
            "projeto": projetos.get(p.get("projetoId"), ""),
            "prioridade": p.get("prioridade", "media"),
            "prazo": prazo,
            "prazoObs": prazo_obs,
            "atrasada": bool(p.get("atrasada")),
        })

    # Mais urgente primeiro: com prazo (data mais cedo) → sem prazo; empate
    # decidido pela prioridade.
    lista.sort(key=lambda i: (i["prazo"] is None, i["prazo"] or "",
                              PRIORIDADE_ORDEM.get(i["prioridade"], 1)))
    return lista


# ================= MINHAS PENDÊNCIAS =================

def carregar_minhas():
    return ler_json(ARQ_MINHAS, [])


def salvar_minhas(lista):
    gravar_json(ARQ_MINHAS, lista)


def data_br_para_iso(texto):
    """'25/09/2026' ou '25/09' → '2026-09-25'. Vazio → None. Inválido → ValueError."""
    texto = texto.strip()
    if not texto:
        return None
    partes = texto.split("/")
    if len(partes) == 2:
        partes.append(str(date.today().year))
    dia, mes, ano = (int(x) for x in partes)
    if ano < 100:
        ano += 2000
    return date(ano, mes, dia).isoformat()


def data_iso_para_br(iso):
    if not iso:
        return ""
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")


# ================= JANELA =================

class App:
    def __init__(self, raiz, config):
        self.raiz = raiz
        self.config = config
        self.minhas = carregar_minhas()
        self.flow = []
        self.mtime_flow = None
        self.baixando = False

        raiz.title("Minhas Pendências")
        # Tamanho que cabe na tela: em telas pequenas (ou com zoom do Windows
        # em 150%), 640 de altura passava da borda e escondia os botões.
        largura = min(760, raiz.winfo_screenwidth() - 40)
        altura = min(640, raiz.winfo_screenheight() - 90)  # 90 = barra de tarefas + título
        x = (raiz.winfo_screenwidth() - largura) // 2
        raiz.geometry(f"{largura}x{altura}+{x}+20")
        raiz.minsize(520, 380)

        estilo = ttk.Style()
        estilo.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        self.titulo = tk.Label(raiz, text="", font=("Segoe UI", 15, "bold"), anchor="w")
        self.titulo.pack(fill="x", padx=14, pady=(12, 2))
        self.resumo = tk.Label(raiz, text="", font=("Segoe UI", 10), fg="#555", anchor="w")
        self.resumo.pack(fill="x", padx=14, pady=(0, 8))

        # ---- Do Flow ----
        cab = tk.Frame(raiz)
        cab.pack(fill="x", padx=14)
        tk.Label(cab, text="Do Flow (atas)", font=("Segoe UI", 12, "bold")).pack(side="left")
        self.botao_atualizar = ttk.Button(cab, text="Atualizar", command=lambda: self.atualizar_flow(pode_abrir_login=True))
        self.botao_atualizar.pack(side="right")

        self.arvore_flow = self.nova_tabela(raiz, [
            ("texto", "Atividade", 330), ("projeto", "Projeto", 130),
            ("prazo", "Prazo", 170), ("prio", "Prioridade", 80),
        ], altura=5)
        self.aviso_flow = tk.Label(raiz, text="", fg="#b00020", anchor="w", justify="left")
        self.aviso_flow.pack(fill="x", padx=14)
        self.rodape_flow = tk.Label(raiz, text="", font=("Segoe UI", 9), fg="#777", anchor="w")
        self.rodape_flow.pack(fill="x", padx=14, pady=(0, 10))

        # ---- Minhas ----
        tk.Label(raiz, text="Minhas pendências", font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=14)
        linha = tk.Frame(raiz)
        linha.pack(fill="x", padx=14, pady=4)
        self.campo_texto = ttk.Entry(linha, font=("Segoe UI", 10))
        self.campo_texto.pack(side="left", fill="x", expand=True)
        self.campo_texto.bind("<Return>", lambda e: self.adicionar())
        tk.Label(linha, text=" Prazo:").pack(side="left")
        self.campo_prazo = ttk.Entry(linha, width=11, font=("Segoe UI", 10))
        self.campo_prazo.pack(side="left")
        self.campo_prazo.bind("<Return>", lambda e: self.adicionar())
        ttk.Button(linha, text="Adicionar", command=self.adicionar).pack(side="left", padx=(6, 0))
        tk.Label(raiz, text="Prazo é opcional (dd/mm ou dd/mm/aaaa). Enter também adiciona.",
                 font=("Segoe UI", 9), fg="#777", anchor="w").pack(fill="x", padx=14)

        # Os botões são presos no RODAPÉ antes de criar a tabela: assim a
        # tabela só ocupa o espaço que sobra e nunca empurra os botões para
        # fora da janela.
        botoes = tk.Frame(raiz)
        botoes.pack(side="bottom", fill="x", padx=14, pady=(4, 12))
        ttk.Button(botoes, text="✔ Feito / desfazer", command=self.alternar_feito).pack(side="left")
        ttk.Button(botoes, text="✎ Editar", command=self.editar).pack(side="left", padx=(6, 0))
        ttk.Button(botoes, text="Excluir", command=self.excluir).pack(side="left", padx=6)
        ttk.Button(botoes, text="Limpar concluídas", command=self.limpar_concluidas).pack(side="left")

        self.arvore_minhas = self.nova_tabela(raiz, [
            ("feito", "", 30), ("texto", "Pendência", 480), ("prazo", "Prazo", 120),
        ], altura=8, expandir=True)
        self.arvore_minhas.bind("<Double-1>", lambda e: self.alternar_feito())
        self.arvore_minhas.bind("<space>", lambda e: self.alternar_feito())
        self.arvore_minhas.bind("<Delete>", lambda e: self.excluir())
        self.arvore_minhas.bind("<F2>", lambda e: self.editar())

        self.mostrar_titulo()
        self.mostrar_minhas()
        if config["fonte"] == "site":
            self.mostrar_cache()
            self.atualizar_flow(pode_abrir_login=True)
            self.baixar_de_tempos_em_tempos()
        else:
            self.atualizar_flow()
            self.vigiar_arquivo()
        self.campo_texto.focus_set()
        self.faixa_atualizacao = None
        self.servidor = None  # main() preenche; é fechado antes de reabrir
        self.verificar_atualizacao()
        # Se uma atualização trouxe um instalar.ps1 novo, aplica (escondido).
        threading.Thread(target=aplicar_instalador_se_mudou, daemon=True).start()

    # ---- Atualização ----
    def verificar_atualizacao(self):
        # Numa linha paralela: sem internet, o GitHub demora e a janela não
        # pode travar esperando.
        def trabalho():
            nova = versao_nova_disponivel()
            if nova:
                self.raiz.after(0, lambda: self.mostrar_faixa_atualizacao(nova))

        threading.Thread(target=trabalho, daemon=True).start()

    def mostrar_faixa_atualizacao(self, nova):
        if self.faixa_atualizacao:
            return
        faixa = tk.Frame(self.raiz, bg="#fff4c2")
        faixa.pack(fill="x", before=self.titulo)
        tk.Label(faixa, text=f"Há uma versão nova do app ({nova}). Você está com a {VERSAO}.",
                 bg="#fff4c2", font=("Segoe UI", 10)).pack(side="left", padx=14, pady=6)
        ttk.Button(faixa, text="Atualizar agora", command=self.atualizar_app).pack(side="right", padx=14, pady=6)
        self.faixa_atualizacao = faixa

    def atualizar_app(self):
        try:
            instalar_versao_nova()
        except Exception as e:
            messagebox.showerror("Atualizar", f"Não consegui atualizar agora:\n{e}\n\n"
                                              "Nada foi trocado. Tente de novo mais tarde.")
            return
        messagebox.showinfo("Atualizar", "App atualizado! Ele vai abrir de novo agora.")
        # Solta a porta de "uma janela só" antes de abrir a versão nova, senão
        # ela acharia que ainda tem uma janela aberta e fecharia.
        if self.servidor:
            self.servidor.close()
        subprocess.Popen([sys.executable, os.path.join(PASTA, "pendencias.pyw")], cwd=PASTA)
        self.raiz.destroy()

    def mostrar_titulo(self):
        hoje = date.today()
        nome = self.config["meuNome"] or ler_json(ARQ_CACHE, {}).get("nome", "")
        saudacao = f"Olá, {nome}!" if nome else "Olá!"
        self.titulo.config(text=f"{saudacao}  {DIAS_SEMANA[hoje.weekday()]}, {hoje.strftime('%d/%m/%Y')}")

    def nova_tabela(self, pai, colunas, altura, expandir=False):
        quadro = tk.Frame(pai)
        quadro.pack(fill="both", expand=expandir, padx=14, pady=4)
        arvore = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings", height=altura)
        for chave, titulo, largura in colunas:
            arvore.heading(chave, text=titulo, anchor="w")
            arvore.column(chave, width=largura, anchor="w", stretch=(chave == "texto"))
        rolagem = ttk.Scrollbar(quadro, orient="vertical", command=arvore.yview)
        arvore.configure(yscrollcommand=rolagem.set)
        arvore.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        arvore.tag_configure("vencida", foreground="#b00020")
        arvore.tag_configure("hoje", foreground="#cd3900")
        arvore.tag_configure("feita", foreground="#999")
        return arvore

    def tag_do_prazo(self, prazo_iso, atrasada=False):
        hoje = date.today().isoformat()
        if atrasada or (prazo_iso and prazo_iso < hoje):
            return "vencida"
        if prazo_iso == hoje:
            return "hoje"
        return ""

    # ---- Flow ----
    def atualizar_flow(self, pode_abrir_login=False):
        if self.config["fonte"] == "arquivo":
            try:
                dados = dados_do_arquivo(self.config)
            except RuntimeError as e:
                self.mostrar_flow([], str(e))
                return
            nome = self.config["meuNome"]
            aviso = None if nome else 'Preencha "meuNome" no config.json.'
            self.mostrar_flow(pendencias_da_pessoa(dados, nome) if nome else [], aviso)
            self.rodape_flow.config(text="Para concluir estas, use o app de Atas.")
            return

        # Modo "site": baixa numa linha paralela (pode demorar, ou esperar o
        # login no navegador) para a janela não travar.
        if self.baixando:
            return
        self.baixando = True
        self.botao_atualizar.config(state="disabled")
        self.rodape_flow.config(text="Buscando no site do Flow… (se o navegador abrir, faça o login)")

        def trabalho():
            try:
                dados, email = dados_do_site(self.config, pode_abrir_login)
                resultado = ("ok", dados, email)
            except PrecisaLogin:
                resultado = ("login", None, None)
            except Exception as e:
                resultado = ("erro", str(e) or e.__class__.__name__, None)
            self.raiz.after(0, lambda: self.terminou_download(*resultado))

        threading.Thread(target=trabalho, daemon=True).start()

    def terminou_download(self, situacao, dados, email):
        self.baixando = False
        self.botao_atualizar.config(state="normal")
        if situacao == "ok":
            nome = self.config["meuNome"] or nome_pelo_email(dados, email)
            gravar_json(ARQ_CACHE, {
                "baixadoEm": datetime.now().isoformat(timespec="minutes"),
                "email": email, "nome": nome, "dados": dados,
            })
            self.mostrar_titulo()
            self.mostrar_cache()
            return
        self.mostrar_cache()
        if situacao == "login":
            aviso = "Seu login no Flow venceu. Clique em Atualizar para entrar de novo."
        else:
            aviso = f"Não consegui buscar no site agora: {dados}"
        cache = ler_json(ARQ_CACHE, None)
        if cache:
            aviso += "\nMostrando a última versão baixada."
        self.aviso_flow.config(text=aviso, fg="#b00020")

    def mostrar_cache(self):
        cache = ler_json(ARQ_CACHE, None)
        if not cache:
            self.mostrar_flow([], None)
            self.rodape_flow.config(text="")
            return
        nome = self.config["meuNome"] or cache.get("nome", "")
        if not nome:
            email = cache.get("email") or "(sem e-mail)"
            self.mostrar_flow([], f"Seu e-mail {email} não está cadastrado na equipe do Flow.\n"
                                  'Peça para a editora cadastrar, ou preencha "meuNome" no config.json.')
        else:
            self.mostrar_flow(pendencias_da_pessoa(cache["dados"], nome), None)
        quando = datetime.fromisoformat(cache["baixadoEm"]).strftime("%d/%m às %H:%M")
        self.rodape_flow.config(text=f"Versão publicada do Flow, baixada em {quando}. Para concluir, use o site do Flow.")

    def mostrar_flow(self, lista, aviso):
        self.flow = lista
        self.arvore_flow.delete(*self.arvore_flow.get_children())
        for item in lista:
            prazo = data_iso_para_br(item["prazo"])
            if item["prazoObs"]:
                prazo = f"{prazo} ({item['prazoObs']})" if prazo else item["prazoObs"]
            if item["atrasada"]:
                prazo = "⚠ atrasada " + prazo
            self.arvore_flow.insert("", "end", tags=(self.tag_do_prazo(item["prazo"], item["atrasada"]),), values=(
                item["texto"], item["projeto"], prazo, PRIORIDADE_TEXTO.get(item["prioridade"], "")))
        if aviso:
            self.aviso_flow.config(text=aviso, fg="#b00020")
        elif not lista:
            self.aviso_flow.config(text="Nenhuma atividade em aberto no seu nome. 🎉", fg="#2e7d32")
        else:
            self.aviso_flow.config(text="")
        self.atualizar_resumo()

    def vigiar_arquivo(self):
        # A cada 30 s confere se o dados.json mudou (você salvou algo no app de
        # Atas, ou o Drive trouxe uma versão nova) e recarrega sozinho.
        try:
            mtime = os.path.getmtime(self.config["dadosFlow"])
        except OSError:
            mtime = None
        if self.mtime_flow is not None and mtime != self.mtime_flow:
            self.atualizar_flow()
        self.mtime_flow = mtime
        self.raiz.after(30_000, self.vigiar_arquivo)

    def baixar_de_tempos_em_tempos(self):
        # Sem abrir o navegador por conta própria: se o login vencer, só avisa.
        self.raiz.after(MINUTOS_ENTRE_DOWNLOADS * 60_000, self.baixar_de_tempos_em_tempos)
        if not self.baixando and self.raiz.winfo_exists():
            self.atualizar_flow(pode_abrir_login=False)

    # ---- Minhas ----
    def mostrar_minhas(self):
        self.arvore_minhas.delete(*self.arvore_minhas.get_children())
        # Abertas primeiro (por prazo), concluídas no fim.
        ordem = sorted(range(len(self.minhas)), key=lambda i: (
            self.minhas[i]["feito"], self.minhas[i].get("prazo") is None, self.minhas[i].get("prazo") or ""))
        for i in ordem:
            p = self.minhas[i]
            tag = "feita" if p["feito"] else self.tag_do_prazo(p.get("prazo"))
            self.arvore_minhas.insert("", "end", iid=p["id"], tags=(tag,), values=(
                "✔" if p["feito"] else "☐", p["texto"], data_iso_para_br(p.get("prazo"))))
        self.atualizar_resumo()

    def adicionar(self):
        texto = self.campo_texto.get().strip()
        if not texto:
            self.campo_texto.focus_set()
            return
        try:
            prazo = data_br_para_iso(self.campo_prazo.get())
        except ValueError:
            messagebox.showwarning("Prazo inválido", "Use dd/mm ou dd/mm/aaaa (ou deixe em branco).")
            self.campo_prazo.focus_set()
            return
        self.minhas.append({
            "id": datetime.now().strftime("m%Y%m%d%H%M%S%f"),
            "texto": texto,
            "prazo": prazo,
            "feito": False,
            "criadaEm": datetime.now().isoformat(timespec="seconds"),
        })
        salvar_minhas(self.minhas)
        self.campo_texto.delete(0, "end")
        self.campo_prazo.delete(0, "end")
        self.mostrar_minhas()
        self.campo_texto.focus_set()

    def selecionadas(self):
        ids = set(self.arvore_minhas.selection())
        return [p for p in self.minhas if p["id"] in ids]

    def alternar_feito(self):
        for p in self.selecionadas():
            p["feito"] = not p["feito"]
        salvar_minhas(self.minhas)
        self.mostrar_minhas()

    def editar(self):
        # Abre uma janelinha para mudar o texto e o prazo da pendência
        # selecionada (se houver várias selecionadas, edita a primeira).
        escolhidas = self.selecionadas()
        if not escolhidas:
            messagebox.showinfo("Editar", "Selecione uma pendência na lista primeiro.")
            return
        p = escolhidas[0]

        janela = tk.Toplevel(self.raiz)
        janela.title("Editar pendência")
        janela.transient(self.raiz)
        janela.resizable(True, False)
        janela.grab_set()  # enquanto edita, a janela principal fica em espera

        tk.Label(janela, text="Pendência:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        campo_texto = ttk.Entry(janela, width=60, font=("Segoe UI", 10))
        campo_texto.grid(row=0, column=1, sticky="we", padx=(0, 12), pady=(12, 4))
        campo_texto.insert(0, p["texto"])

        tk.Label(janela, text="Prazo:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        campo_prazo = ttk.Entry(janela, width=12, font=("Segoe UI", 10))
        campo_prazo.grid(row=1, column=1, sticky="w", pady=4)
        campo_prazo.insert(0, data_iso_para_br(p.get("prazo")))
        tk.Label(janela, text="dd/mm ou dd/mm/aaaa — deixe em branco para ficar sem prazo.",
                 font=("Segoe UI", 9), fg="#777").grid(row=2, column=1, sticky="w")
        janela.columnconfigure(1, weight=1)

        def salvar():
            texto = campo_texto.get().strip()
            if not texto:
                messagebox.showwarning("Editar", "A pendência não pode ficar sem texto.", parent=janela)
                campo_texto.focus_set()
                return
            try:
                prazo = data_br_para_iso(campo_prazo.get())
            except ValueError:
                messagebox.showwarning("Prazo inválido", "Use dd/mm ou dd/mm/aaaa (ou deixe em branco).",
                                       parent=janela)
                campo_prazo.focus_set()
                return
            p["texto"] = texto
            p["prazo"] = prazo
            salvar_minhas(self.minhas)
            janela.destroy()
            self.mostrar_minhas()
            self.arvore_minhas.selection_set(p["id"])

        botoes = tk.Frame(janela)
        botoes.grid(row=3, column=0, columnspan=2, sticky="e", padx=12, pady=12)
        ttk.Button(botoes, text="Salvar", command=salvar).pack(side="left")
        ttk.Button(botoes, text="Cancelar", command=janela.destroy).pack(side="left", padx=(6, 0))

        janela.bind("<Return>", lambda e: salvar())
        janela.bind("<Escape>", lambda e: janela.destroy())
        campo_texto.focus_set()
        campo_texto.select_range(0, "end")

    def excluir(self):
        escolhidas = self.selecionadas()
        if not escolhidas:
            return
        if not messagebox.askyesno("Excluir", f"Excluir {len(escolhidas)} pendência(s)?"):
            return
        ids = {p["id"] for p in escolhidas}
        self.minhas = [p for p in self.minhas if p["id"] not in ids]
        salvar_minhas(self.minhas)
        self.mostrar_minhas()

    def limpar_concluidas(self):
        feitas = [p for p in self.minhas if p["feito"]]
        if not feitas:
            return
        if not messagebox.askyesno("Limpar", f"Remover {len(feitas)} pendência(s) concluída(s)?"):
            return
        self.minhas = [p for p in self.minhas if not p["feito"]]
        salvar_minhas(self.minhas)
        self.mostrar_minhas()

    def atualizar_resumo(self):
        hoje = date.today().isoformat()
        abertas = [p for p in self.minhas if not p["feito"]]
        prazos = [i["prazo"] for i in self.flow] + [p.get("prazo") for p in abertas]
        vencidas = sum(1 for d in prazos if d and d < hoje) + sum(1 for i in self.flow if i["atrasada"])
        para_hoje = sum(1 for d in prazos if d == hoje)
        texto = f"{len(self.flow)} do Flow  ·  {len(abertas)} suas em aberto"
        if para_hoje:
            texto += f"  ·  {para_hoje} para hoje"
        if vencidas:
            texto += f"  ·  {vencidas} vencida(s)"
        self.resumo.config(text=texto)

    def trazer_para_frente(self):
        self.raiz.deiconify()
        self.raiz.lift()
        self.raiz.attributes("-topmost", True)
        self.raiz.after(800, lambda: self.raiz.attributes("-topmost", False))
        self.raiz.focus_force()
        self.atualizar_flow(pode_abrir_login=True)
        self.verificar_atualizacao()  # a janela pode estar aberta há dias


# ================= UMA JANELA SÓ =================

def avisar_janela_aberta():
    """Se já existe uma janela, pede para ela aparecer e devolve True."""
    try:
        with socket.create_connection(("127.0.0.1", PORTA_UNICA), timeout=1) as s:
            s.sendall(b"mostrar")
        return True
    except OSError:
        return False


def escutar_pedidos(app, servidor):
    while True:
        try:
            conexao, _ = servidor.accept()
            conexao.close()
            app.raiz.after(0, app.trazer_para_frente)
        except OSError:
            return


def main():
    automatico = "--auto" in sys.argv
    if automatico and ja_abriu_hoje():
        return
    if avisar_janela_aberta():
        # A janela já estava aberta (talvez desde ontem): ela vem para frente.
        marcar_aberto_hoje()
        return

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        servidor.bind(("127.0.0.1", PORTA_UNICA))
    except OSError:
        return  # outra cópia abriu no mesmo instante
    servidor.listen()

    marcar_aberto_hoje()
    raiz = tk.Tk()
    app = App(raiz, carregar_config())
    app.servidor = servidor
    threading.Thread(target=escutar_pedidos, args=(app, servidor), daemon=True).start()
    raiz.deiconify()
    raiz.lift()
    raiz.attributes("-topmost", True)
    raiz.after(800, lambda: raiz.attributes("-topmost", False))
    raiz.focus_force()
    raiz.mainloop()


if __name__ == "__main__":
    main()
