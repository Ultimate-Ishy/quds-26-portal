import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, timedelta

# --- 1. データベース基本操作 ---
DB_FILE = "debate_app.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, pw TEXT, role TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS attendance 
                     (user_id TEXT, user_name TEXT, week_id TEXT, slot TEXT, mode TEXT, 
                      pref TEXT, note TEXT, motion TEXT, PRIMARY KEY(user_id, week_id, slot))''')
        c.execute('''CREATE TABLE IF NOT EXISTS allocs (week_id TEXT PRIMARY KEY, content TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS schedule 
                     (date TEXT PRIMARY KEY, is_active TEXT, start_time TEXT, motion_type TEXT)''')
        
        c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'admin')")
        c.execute("INSERT OR IGNORE INTO users VALUES ('QUDS26', 'EnjoyItoshimaLife', 'member')")

def exec_query(sql, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        conn.cursor().execute(sql, params)
        conn.commit()

def get_query(sql, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql(sql, conn, params=params)

# --- 2. 認証 ---
st.set_page_config(page_title="QUDS Management System", layout="wide")
if 'login' not in st.session_state: st.session_state.login = False

def login_ui():
    st.title("🔑 QUDS Portal Login")
    user = st.text_input("ID")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        res = get_query("SELECT * FROM users WHERE id=? AND pw=?", (user, pw))
        if not res.empty:
            st.session_state.login, st.session_state.user_id, st.session_state.role = True, user, res.iloc[0]['role']
            st.rerun()
        else: st.error("IDまたはパスワードが違います")

# --- 3. メインロジック ---
def main():
    init_db()
    if not st.session_state.login:
        login_ui()
        return

    st.sidebar.title(f"👤 {st.session_state.user_id}")
    if st.sidebar.button("Logout"):
        st.session_state.login = False
        st.rerun()

    today = datetime.now()
    this_week = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    
    tab_cal, tab_attend, tab_view, tab_admin = st.tabs(["📅 月間予定表", "📝 出席登録", "📊 アロケ確認", "⚙️ 管理パネル"])

    # --- A. 月間予定表 ---
    with tab_cal:
        st.subheader("🗓 月間スケジュール")
        col_m1, col_m2 = st.columns([1, 4])
        with col_m1:
            target_date = st.date_input("年月を選択", today)
            year, month = target_date.year, target_date.month
        
        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdayscalendar(year, month)
        
        cols = st.columns(7)
        days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for i, d in enumerate(days): cols[i].write(f"**{d}**")
        
        sched_df = get_query("SELECT * FROM schedule WHERE date LIKE ?", (f"{year}-{month:02d}%",))
        sched_dict = {row['date']: row for _, row in sched_df.iterrows()}

        for week in month_days:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("")
                else:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    cell = cols[i].container(border=True)
                    cell.write(f"**{day}**")
                    if date_str in sched_dict:
                        s = sched_dict[date_str]
                        if s['is_active'] == "Yes":
                            cell.caption(f"⏰{s['start_time']}")
                            cell.caption(f"🏷{s['motion_type']}")
                        else: cell.caption("OFF")

        if st.session_state.role == "admin":
            st.divider()
            with st.expander("🛠 スケジュールを編集（Admin専用）"):
                edit_date = st.date_input("編集する日付", target_date)
                e_col1, e_col2 = st.columns(2)
                is_act = e_col1.radio("練習の有無", ["Yes", "No"])
                s_time = e_col2.text_input("開始時刻", "18:00")
                
                # 指定された24個のMotion Type
                motion_categories = [
                    "Art", "Choice", "CJS", "Conflicts", "Economy (Corporations)", 
                    "Economy (Development)", "Economy (Finance and Governments)", 
                    "Education", "Environment", "E-Sports", "Feminism", 
                    "International Relations (General)", "LGBTQ", "Media", 
                    "Medical Ethics", "Minority", "Narrative", "Parents", 
                    "Politics", "Philosophy", "Relationships", "Religion", 
                    "Sports", "Technology"
                ]
                m_type = st.selectbox("Motion Type", motion_categories)
                
                if st.button("予定を保存"):
                    exec_query("INSERT OR REPLACE INTO schedule VALUES (?,?,?,?)", 
                               (edit_date.strftime("%Y-%m-%d"), is_act, s_time, m_type))
                    st.success(f"{edit_date} の予定を更新しました")
                    st.rerun()

    # --- B. 出席登録 ---
    with tab_attend:
        st.subheader("📝 今週の出席登録")
        user_name = st.text_input("名前", key="user_name_input")
        slots = ["Wed 1", "Wed 2", "Thu 1", "Sun 1", "Sun 2"]
        results = []
        for s in slots:
            with st.expander(f"🕒 {s}", expanded=True):
                col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
                with col1: attend = st.checkbox("参加", key=f"at_{s}")
                with col2: mode = st.selectbox("形態", ["Offline", "Online"], key=f"md_{s}")
                with col3: pref = st.selectbox("役割", ["Debater", "Judge", "Audience", "Any"], key=f"rf_{s}")
                with col4: note = st.text_input("備考", key=f"nt_{s}")
                motion = st.text_input(f"💡 {s} のMotion案", key=f"mot_{s}") if attend and pref == "Judge" else ""
                if attend: results.append((st.session_state.user_id, user_name, this_week, s, mode, pref, note, motion))

        if st.button("出席回答を確定"):
            if not user_name: st.error("名前を入力してください")
            else:
                exec_query("DELETE FROM attendance WHERE user_id=? AND week_id=?", (st.session_state.user_id, this_week))
                for r in results: exec_query("INSERT INTO attendance VALUES (?,?,?,?,?,?,?,?)", r)
                st.success("回答を保存しました！")

    # --- C. アロケ確認 ---
    with tab_view:
        st.subheader("📢 確定アロケーション")
        alloc_res = get_query("SELECT content FROM allocs WHERE week_id=?", (this_week,))
        if not alloc_res.empty: st.markdown(alloc_res.iloc[0]['content'])
        else: st.info("公開待ちです。")

    # --- D. 管理パネル ---
    with tab_admin:
        if st.session_state.role != "admin": st.error("管理者権限が必要です")
        else:
            st.subheader("📋 メンバー回答一覧")
            # User IDを除外し、名前・スロット順に並び替えて取得
            all_data = get_query("""
                SELECT user_name as '名前', slot as '日時', mode as '形態', 
                       pref as '役割', note as '備考', motion as 'Motion案' 
                FROM attendance 
                WHERE week_id=? 
                ORDER BY slot ASC, user_name ASC
            """, (this_week,))
            
            if not all_data.empty:
                st.dataframe(all_data, use_container_width=True)
            else:
                st.write("今週の回答はまだありません。")

            st.divider()
            st.subheader("🛠 アロケ作成ガイド")
            fmt = st.selectbox("フォーマット選択", ["NA", "BP", "BP opening", "AP"])
            if st.button("テンプレート生成"):
                req = {"NA":4, "BP":8, "BP opening":4, "AP":6}[fmt]
                rooms = len(all_data) // req
                temp = f"### {fmt} Allocations\n" + (f"**Room**\n| Role | Name |\n|---|---|\n" * rooms)
                st.session_state.alloc_temp = temp
            
            final_content = st.text_area("編集", value=st.session_state.get('alloc_temp', ""), height=300)
            if st.button("公開"):
                exec_query("INSERT OR REPLACE INTO allocs VALUES (?, ?)", (this_week, final_content))
                st.success("公開完了")

if __name__ == "__main__":
    main()