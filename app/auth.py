import os
import streamlit as st
import streamlit_authenticator as stauth
import json


def login():
    # Leemos credenciales del env y las cargamos como dict
    creds_raw = os.getenv("APP_CREDENTIALS", "{}")
    try:
        credentials_dict = json.loads(creds_raw)
    except json.JSONDecodeError:
        st.error("Error en APP_CREDENTIALS. Debe ser un JSON válido.")
        st.stop()

    # Creamos el formato requerido por la librería
    credentials = {
        "usernames": {
            user: {
                "name": user.capitalize(),
                "password": password
            }
            for user, password in credentials_dict.items()
        }
    }

    authenticator = stauth.Authenticate(
        credentials,
        "planning_app",
        "abcdef",
        cookie_expiry_days=1
    )

    name, status, _ = authenticator.login(
        "main",
        fields={
            "Form name": "Iniciar sesión",
            "Username": "Usuario",
            "Password": "Contraseña",
            "Login": "Acceder",
        }
    )

    if status is False:
        st.error("Usuario o contraseña incorrectos")
    elif status is None:
        st.warning("Introduzca sus credenciales")

    return status