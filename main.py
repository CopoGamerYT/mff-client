import customtkinter as ctk
import requests
from PIL import Image
import io
import json
import webbrowser
from urllib.parse import urlparse, parse_qs
import minecraft_launcher_lib
import socket
import threading

# Configuración básica
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- SIMULACIÓN DEL JSON EN LA NUBE ---
JSON_NUBE = """
{
    "series": [
        {
            "id": "serie-1",
            "nombre": "Serie 1",
            "mantenimiento": true,
            "color_estado": "orange"
        },
        {
            "id": "cobbleverse",
            "nombre": "Cobbleverse",
            "mantenimiento": false,
            "color_estado": "#00FF00"
        },
        {
            "id": "serie-3",
            "nombre": "Serie 3 (Pruebas)",
            "mantenimiento": true,
            "color_estado": "red"
        }
    ]
}
"""

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text: return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 10
        y = self.widget.winfo_rooty() + (self.widget.winfo_height() // 2) - 15
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.attributes("-topmost", True)
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, fg_color="#333333", text_color="white", corner_radius=6, padx=10, pady=5)
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login - MFF")
        self.geometry("400x450")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self, text="Bienvenido", font=ctk.CTkFont(size=30, weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=(40, 20))
        
        self.btn_microsoft = ctk.CTkButton(self, text="Iniciar con Microsoft", command=self.login_microsoft, fg_color="#107c10", hover_color="#054c05", font=ctk.CTkFont(size=16, weight="bold"), height=45)
        self.btn_microsoft.grid(row=1, column=0, pady=(0, 40), padx=40, sticky="ew")
        
        self.lbl_sep = ctk.CTkLabel(self, text="--- O jugar offline (No Premium) ---", text_color="gray")
        self.lbl_sep.grid(row=2, column=0, pady=(0, 20))
        
        self.entry_username = ctk.CTkEntry(self, placeholder_text="Tu nombre de usuario...", height=45, font=ctk.CTkFont(size=14))
        self.entry_username.grid(row=3, column=0, pady=(0, 15), padx=40, sticky="ew")
        
        self.btn_offline = ctk.CTkButton(self, text="Jugar Offline", command=self.login_offline, height=45, font=ctk.CTkFont(size=16, weight="bold"))
        self.btn_offline.grid(row=4, column=0, padx=40, sticky="ew")
        
    def login_offline(self):
        username = self.entry_username.get()
        if username.strip() == "": return
        self.destroy()
        app = EventLauncher(username, is_premium=False)
        app.mainloop()

    # --- LÓGICA DE MICROSOFT AUTOMÁTICA ---
    def login_microsoft(self):
        # ¡Extraje tu ID exacto de la captura que enviaste!
        self.client_id = "98df4add-0840-40d5-a0ee-1a571026cc99" 
        self.redirect_url = "http://localhost:8080/login"
        
        self.btn_microsoft.configure(text="Revisa tu navegador...", state="disabled")
        self.update()
        
        # Generamos URL y abrimos navegador
        login_url, self.state, self.code_verifier = minecraft_launcher_lib.microsoft_account.get_secure_login_data(self.client_id, self.redirect_url)
        webbrowser.open(login_url)
        
        # Iniciamos el servidor fantasma en un "hilo" invisible
        threading.Thread(target=self.servidor_fantasma, daemon=True).start()

        
    def servidor_fantasma(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        
        class LoginHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Le respondemos al navegador con la pantalla de éxito
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                html = "<html><body style='background-color:#2b2b2b; color:white; text-align:center; font-family:sans-serif; margin-top:50px;'><h1>¡Login Exitoso!</h1><p>Ya puedes cerrar esta pestaña y volver al MFF Launcher.</p></body></html>"
                self.wfile.write(html.encode('utf-8'))
                
                # Guardamos la ruta que nos mandó Microsoft
                self.server.auth_path = self.path
                
            def log_message(self, format, *args):
                pass # Esto evita que se llene tu consola de texto innecesario
        
        try:
            # Levantamos el servidor HTTP robusto
            # Las comillas vacías '' hacen que escuche en todos los canales de red, evitando bloqueos de Windows
            server = HTTPServer(('', 8080), LoginHandler)
            server.auth_path = None
            
            # EL BUCLE MÁGICO: Ignora la "basura" del navegador y solo avanza cuando ve el código de Microsoft
            while not server.auth_path or "code=" not in server.auth_path:
                server.handle_request()
                
            # Extraemos la URL y apagamos el servidor correctamente
            full_url = f"http://localhost:8080{server.auth_path}"
            server.server_close()
            
            # Le pasamos la URL validada al launcher
            self.completar_microsoft_automatico(full_url)
            
        except Exception as e:
            print("Error en el servidor fantasma:", e)

    def completar_microsoft_automatico(self, url_devuelta):
        try:
            auth_code = minecraft_launcher_lib.microsoft_account.parse_auth_code_url(url_devuelta, self.state)
            account_data = minecraft_launcher_lib.microsoft_account.complete_login(
                self.client_id, None, self.redirect_url, auth_code, self.code_verifier
            )
            
            username = account_data["name"]
            print(f"¡Login Premium Exitoso! Bienvenido, {username}")
            
            self.after(0, self.iniciar_launcher, username)
            
        except Exception as e:
            print("Error al validar con Microsoft:", e)
            self.after(0, lambda: self.btn_microsoft.configure(text="Error. Intenta de nuevo", state="normal", fg_color="#cc0000"))

    def iniciar_launcher(self, username):
        self.destroy()
        app = EventLauncher(username, is_premium=True)
        app.mainloop()


class EventLauncher(ctk.CTk):
    def __init__(self, username, is_premium):
        super().__init__()
        self.title("MFF Launcher")
        self.geometry("900x600")
        self.resizable(False, False)
        self.username = username
        self.is_premium = is_premium

        self.config_data = json.loads(JSON_NUBE)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- MENÚ LATERAL ---
        self.sidebar_frame = ctk.CTkFrame(self, width=70, corner_radius=0, fg_color="#2b2b2b")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(1, weight=1)
        self.instances_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.instances_frame.grid(row=0, column=0, sticky="n", pady=10)

        # --- PERFIL DEL USUARIO ---
        self.btn_profile = ctk.CTkButton(self.sidebar_frame, text="", width=45, height=45, corner_radius=10, fg_color="#404040", state="disabled")
        self.btn_profile.grid(row=2, column=0, pady=15, padx=10, sticky="s")
        ToolTip(self.btn_profile, f'Jugador Seleccionado: "{self.username}"')
        self.after(100, self.descargar_skin)

        # --- ÁREA PRINCIPAL ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self.main_frame, text="Cargando...", font=ctk.CTkFont(size=45, weight="bold"))
        self.lbl_title.grid(row=1, column=0, pady=(0, 10))
        self.lbl_status = ctk.CTkLabel(self.main_frame, text="...", font=ctk.CTkFont(size=18))
        self.lbl_status.grid(row=2, column=0, pady=(0, 20))

        # --- BOTONES INFERIORES ---
        self.bottom_buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_buttons_frame.grid(row=3, column=0, sticky="s", pady=40)
        self.btn_play = ctk.CTkButton(self.bottom_buttons_frame, text="JUGAR", font=ctk.CTkFont(size=24, weight="bold"), width=250, height=60, corner_radius=8)
        self.btn_play.pack(side="left", padx=(0, 15))
        self.btn_settings = ctk.CTkButton(self.bottom_buttons_frame, text="⚙️", font=ctk.CTkFont(size=30), width=60, height=60, corner_radius=12)
        self.btn_settings.pack(side="left")

        # Cargamos los botones
        self.cargar_instancias(self.config_data["series"])

    def cargar_instancias(self, lista_series):
        max_mostrar = min(len(lista_series), 8)
        for i in range(max_mostrar):
            serie_actual = lista_series[i]
            if i == 7 and len(lista_series) > 8:
                btn = ctk.CTkButton(self.instances_frame, text="...", font=ctk.CTkFont(size=20, weight="bold"), width=45, height=45, fg_color="gray", text_color="white", corner_radius=10)
                ToolTip(btn, "Ver todas las instancias")
            else:
                btn = ctk.CTkButton(self.instances_frame, text="", width=45, height=45, fg_color="gray", corner_radius=10, 
                                    command=lambda s=serie_actual: self.seleccionar_serie(s))
                ToolTip(btn, serie_actual["nombre"])
            btn.pack(pady=8, padx=10)
            
        if len(lista_series) > 0:
            self.seleccionar_serie(lista_series[0])

    def seleccionar_serie(self, datos_serie):
        self.lbl_title.configure(text=datos_serie["nombre"])
        
        if datos_serie["mantenimiento"]:
            self.lbl_status.configure(text="Estado: En Mantenimiento", text_color=datos_serie["color_estado"])
            self.btn_play.configure(state="disabled", fg_color="gray")
        else:
            self.lbl_status.configure(text="Estado: Listo para jugar", text_color=datos_serie["color_estado"])
            self.btn_play.configure(state="normal", fg_color="#1f538d") 

    def descargar_skin(self):
        nombre_a_buscar = self.username
        try:
            url_mojang = f"https://api.mojang.com/users/profiles/minecraft/{nombre_a_buscar}"
            respuesta_mojang = requests.get(url_mojang, timeout=5)
            if respuesta_mojang.status_code != 200:
                url_mojang = "https://api.mojang.com/users/profiles/minecraft/Steve"
                respuesta_mojang = requests.get(url_mojang, timeout=5)
            
            datos_mojang = respuesta_mojang.json()
            uuid_jugador = datos_mojang.get("id")
            url_crafatar = f"https://crafatar.com/avatars/{uuid_jugador}?size=45&overlay"
            respuesta_crafatar = requests.get(url_crafatar, timeout=5)
            
            if respuesta_crafatar.status_code == 200:
                img_data = respuesta_crafatar.content
                pil_image = Image.open(io.BytesIO(img_data))
                ctk_skin_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(45, 45))
                self.btn_profile.configure(image=ctk_skin_image, fg_color="transparent", state="normal")
        except Exception:
            pass

if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()