import streamlit as st
import streamlit.components.v1 as components
import base64
from pathlib import Path


def show_welcome():

    if st.session_state.get("welcome_shown", False):
        return

    st.session_state["welcome_shown"] = True

    # Locate original logo
    logo_path = (
        Path(__file__).parent
        / "inkwise_logo.jpeg"
    )

    # Read logo
    with open(logo_path, "rb") as file:
        logo_data = base64.b64encode(
            file.read()
        ).decode()

    # Splash screen
    components.html(

        f"""
        <!DOCTYPE html>

        <html>

        <head>

        <style>

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            overflow: hidden;
            font-family: Arial, sans-serif;
        }}

        .splash {{

            position: fixed;

            inset: 0;

            width: 100vw;
            height: 100vh;

            background: #192B4D;

            display: flex;

            justify-content: center;
            align-items: center;

            z-index: 999999;

            animation: exit 1s ease-in-out 3s forwards;

        }}

        .logo-container {{

            width: 85%;

            max-width: 900px;

            animation: enter 1s ease-out;

        }}

        .logo {{

            width: 100%;

            height: auto;

            display: block;

        }}

        @keyframes enter {{

            from {{
                opacity: 0;
                transform: scale(0.94);
            }}

            to {{
                opacity: 1;
                transform: scale(1);
            }}

        }}

        @keyframes exit {{

            to {{
                opacity: 0;
                visibility: hidden;
            }}

        }}

        </style>

        </head>

        <body>

        <div class="splash">

            <div class="logo-container">

                <img
                    src="data:image/jpeg;base64,{logo_data}"
                    class="logo"
                >

            </div>

        </div>

        <script>

        setTimeout(function() {{

            window.parent.postMessage(
                {{type: "INKWISE_SPLASH_COMPLETE"}},
                "*"
            );

        }}, 4000);

        </script>

        </body>

        </html>

        """,

        height=800,

        scrolling=False

    )