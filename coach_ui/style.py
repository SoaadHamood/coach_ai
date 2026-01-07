import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
          html, body, .stApp {
            background: radial-gradient(1200px 700px at 15% 10%, #EAF4FF 0%, rgba(234,244,255,0) 55%),
                        radial-gradient(900px 600px at 90% 20%, #E6FBFF 0%, rgba(230,251,255,0) 60%),
                        linear-gradient(180deg, #F9FCFF 0%, #F2F7FF 60%, #F7FBFF 100%) !important;
            color: #0B1220 !important;
          }

          #MainMenu { visibility: hidden; }
          footer { visibility: hidden; }
          header { visibility: hidden; }
          .stDeployButton { display:none !important; }

          .stMarkdown, .stText, .stButton, .stTextInput, .stSelectbox, .stRadio, .stTextArea {
            font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
          }

          .block-container {
            padding-top: 1.1rem;
            padding-bottom: 1.8rem;
            max-width: 1200px;
          }

          :root{
            --text:#0B1220;
            --muted:#5B6B85;
            --stroke: rgba(15, 23, 42, 0.12);
            --shadow: 0 18px 45px rgba(15, 23, 42, 0.10);
            --glass: rgba(255, 255, 255, 0.72);
            --glass2: rgba(255, 255, 255, 0.58);
            --blue:#2F6BFF;
            --cyan:#18B6D4;
            --warn:#F5A524;
            --danger:#EF4444;
            --ok:#22C55E;
          }

          .glass{
            background: var(--glass);
            border: 1px solid var(--stroke);
            box-shadow: var(--shadow);
            border-radius: 18px;
            padding: 18px 18px;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
          }
          .glass.soft{ background: var(--glass2); }

          .section-title{
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 10px;
          }
          .muted{ color: var(--muted); }
          .hint{ margin: 0; color: var(--text); opacity: 0.92; line-height: 1.35; }

          .pill{
            display:inline-flex;
            align-items:center;
            gap:10px;
            padding: 10px 12px;
            border-radius: 999px;
            border: 1px solid var(--stroke);
            background: rgba(255,255,255,0.62);
          }
          .dot{
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: rgba(91,107,133,0.55);
          }

          /* NEW: recording indicator */
          .rec{
            display:inline-flex;
            align-items:center;
            gap:10px;
            padding: 10px 12px;
            border-radius: 999px;
            border: 1px solid rgba(239,68,68,0.20);
            background: rgba(255,255,255,0.75);
            box-shadow: 0 10px 28px rgba(239,68,68,0.10);
          }
          .rec-dot{
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: var(--danger);
            box-shadow: 0 0 0 5px rgba(239,68,68,0.12);
          }

          .badge{
            display:inline-flex;
            align-items:center;
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid var(--stroke);
            background: rgba(255,255,255,0.7);
          }
          .sev-high{ border-color: rgba(239,68,68,0.25); }
          .sev-med{ border-color: rgba(245,165,36,0.25); }
          .sev-low{ border-color: rgba(34,197,94,0.25); }

          /* Transcript box becomes visually secondary */
          .transcript-line{
            padding: 10px 12px;
            border-radius: 14px;
            border: 1px solid rgba(15,23,42,0.10);
            background: rgba(255,255,255,0.55);
            margin-bottom: 8px;
          }
          .speaker{
            font-weight: 800;
            font-size: 12px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 3px;
          }

          /* Coach cards */
          .coach-card{
            padding: 18px;
            border-radius: 18px;
            border: 1px solid rgba(47,107,255,0.20);
            background: rgba(255,255,255,0.78);
            box-shadow: 0 18px 48px rgba(47,107,255,0.10);
          }

          /* NEW: Primary (big) suggestion */
          .coach-primary{
            padding: 22px;
            border-radius: 22px;
            border: 1px solid rgba(47,107,255,0.32);
            background: rgba(255,255,255,0.86);
            box-shadow:
              0 26px 70px rgba(47,107,255,0.16),
              0 0 0 6px rgba(47,107,255,0.06);
          }
          .coach-primary h2{
            margin: 0;
            font-size: 22px;
            letter-spacing: -0.3px;
          }

          /* Simple metric tiles (post-call) */
          .metric-grid{
            display:grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
          }
          .metric-tile{
            padding: 14px;
            border-radius: 16px;
            border: 1px solid rgba(15,23,42,0.10);
            background: rgba(255,255,255,0.70);
          }
          .metric-label{ color: var(--muted); font-size: 12px; font-weight: 800; letter-spacing:0.10em; text-transform:uppercase; }
          .metric-val{ font-size: 18px; font-weight: 900; margin-top: 4px; }

          /* Buttons */
          .stButton>button{
            border-radius: 14px !important;
            padding: 0.78rem 0.95rem !important;
            border: 1px solid rgba(15,23,42,0.12) !important;
            background: rgba(255,255,255,0.75) !important;
          }
          .stButton>button:hover{
            border-color: rgba(47,107,255,0.35) !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
