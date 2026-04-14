import copy from datetime
import date, datetime from typing
import Any, Dict, List

import pandas as pd import streamlit as st

st.set_page_config(page_title="コストテーブルMVP", layout="wide")

-----------------------------

Sample data

-----------------------------

def make_sample_tables() -> List[Dict[str, Any]]: return [ { "id": 1, "table_name": "SUS304 切削部品標準単価表", "item_category": "切削部品", "material": "SUS304", "process": "旋削", "supplier": "A社", "effective_start_date": "2026-04-01", "version": 1, "status": "承認済", "description": "小径シャフト向けの基準単価テーブル", "updated_by": "Ryo", "updated_at": "2026-04-14 09:00", "details": [ { "condition": "外径 0-50 mm", "unit_price": 1200, "correction_factor": 1.00, "note": "標準", }, { "condition": "外径 50-100 mm", "unit_price": 1800, "correction_factor": 1.05, "note": "段取り増", }, ], "evidence": [ { "part_name": "シャフトA", "quantity": 10, "unit_price": 1180, "supplier": "A社", "order_date": "2025-11-10", }, { "part_name": "シャフトB", "quantity": 15, "unit_price": 1210, "supplier": "A社", "order_date": "2025-12-15", }, { "part_name": "シャフトC", "quantity": 8, "unit_price": 1820, "supplier": "A社", "order_date": "2026-01-20", }, { "part_name": "シャフトD", "quantity": 12, "unit_price": 1760, "supplier": "A社", "order_date": "2026-02-04", }, ], "history": [ { "changed_at": "2026-04-14 09:00", "changed_by": "Ryo", "change_summary": "初版承認", } ], }, { "id": 2, "table_name": "SS400 板金部品標準単価表", "item_category": "板金部品", "material": "SS400", "process": "レーザー加工", "supplier": "B社", "effective_start_date": "2026-04-10", "version": 2, "status": "下書き", "description": "薄板部品向け。再見積中。", "updated_by": "Ryo", "updated_at": "2026-04-14 10:30", "details": [ { "condition": "板厚 0-3 mm", "unit_price": 900, "correction_factor": 0.95, "note": "量産前提", }, { "condition": "板厚 3-6 mm", "unit_price": 1400, "correction_factor": 1.00, "note": "標準", }, ], "evidence": [ { "part_name": "ブラケットA", "quantity": 50, "unit_price": 880, "supplier": "B社", "order_date": "2026-02-12", }, { "part_name": "ブラケットB", "quantity": 40, "unit_price": 930, "supplier": "B社", "order_date": "2026-03-01", }, ], "history": [ { "changed_at": "2026-04-14 10:30", "changed_by": "Ryo", "change_summary": "補正係数を見直し中", } ], }, ]

-----------------------------

Session state helpers

-----------------------------

def initialize_state() -> None: if "cost_tables" not in st.session_state: st.session_state.cost_tables = make_sample_tables() if "selected_table_id" not in st.session_state: st.session_state.selected_table_id = st.session_state.cost_tables[0]["id"]

initialize_state()

-----------------------------

Data helpers

-----------------------------

def get_tables() -> List[Dict[str, Any]]: return st.session_state.cost_tables

def get_table_by_id(table_id: int) -> Dict[str, Any] | None: for table in get_tables(): if table["id"] == table_id: return table return None

def get_next_id() -> int: tables = get_tables() if not tables: return 1 return max(t["id"] for t in tables) + 1

def add_history_entry(table: Dict[str, Any], summary: str, user: str = "Ryo") -> None: table.setdefault("history", []).insert( 0, { "changed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "changed_by": user, "change_summary": summary, }, ) table["updated_by"] = user table["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

def validate_table_payload(payload: Dict[str, Any], details_df: pd.DataFrame) -> List[str]: errors: List[str] = []

required_fields = [
    "table_name",
    "item_category",
    "material",
    "process",
    "supplier",
    "effective_start_date",
    "status",
]
for field in required_fields:
    value = payload.get(field)
    if value is None or str(value).strip() == "":
        errors.append(f"必須項目が未入力です: {field}")

if details_df.empty:
    errors.append("明細が1行もありません。")
else:
    for idx, row in details_df.iterrows():
        condition = str(row.get("condition", "")).strip()
        if not condition:
            errors.append(f"明細 {idx + 1} 行目: condition は必須です。")

        unit_price = row.get("unit_price")
        try:
            if float(unit_price) < 0:
                errors.append(f"明細 {idx + 1} 行目: unit_price は0以上にしてください。")
        except Exception:
            errors.append(f"明細 {idx + 1} 行目: unit_price は数値で入力してください。")

        correction_factor = row.get("correction_factor")
        try:
            if float(correction_factor) <= 0:
                errors.append(f"明細 {idx + 1} 行目: correction_factor は0より大きくしてください。")
        except Exception:
            errors.append(f"明細 {idx + 1} 行目: correction_factor は数値で入力してください。")

    duplicated_conditions = details_df[details_df["condition"].astype(str).str.strip().duplicated()]
    if not duplicated_conditions.empty:
        errors.append("condition が重複している明細があります。")

return errors

def serialize_details_df(details_df: pd.DataFrame) -> List[Dict[str, Any]]: cleaned = details_df.fillna("").to_dict(orient="records") results = [] for row in cleaned: results.append( { "condition": str(row.get("condition", "")).strip(), "unit_price": float(row.get("unit_price", 0) or 0), "correction_factor": float(row.get("correction_factor", 1) or 1), "note": str(row.get("note", "")).strip(), } ) return results

def create_or_update_table(table_id: int | None, payload: Dict[str, Any], details_df: pd.DataFrame) -> int: tables = get_tables() details = serialize_details_df(details_df)

if table_id is None:
    new_id = get_next_id()
    new_table = {
        "id": new_id,
        **payload,
        "details": details,
        "evidence": [],
        "history": [],
        "version": int(payload.get("version", 1)),
    }
    add_history_entry(new_table, "新規作成")
    tables.append(new_table)
    return new_id

target = get_table_by_id(table_id)
if target is None:
    raise ValueError("更新対象が見つかりません。")

for key, value in payload.items():
    target[key] = value
target["details"] = details
add_history_entry(target, "内容を更新")
return table_id

def duplicate_table(table_id: int) -> int: source = get_table_by_id(table_id) if source is None: raise ValueError("複製元が見つかりません。")

new_table = copy.deepcopy(source)
new_table["id"] = get_next_id()
new_table["table_name"] = f"{source['table_name']} - コピー"
new_table["status"] = "下書き"
new_table["version"] = int(source.get("version", 1)) + 1
new_table["history"] = []
add_history_entry(new_table, f"ID {table_id} を複製して作成")
st.session_state.cost_tables.append(new_table)
return new_table["id"]

def summarize_evidence(table: Dict[str, Any]) -> Dict[str, float]: evidence = table.get("evidence", []) if not evidence: return {"count": 0, "avg": 0.0, "median": 0.0, "std": 0.0}

df = pd.DataFrame(evidence)
values = pd.to_numeric(df["unit_price"], errors="coerce").dropna()
if values.empty:
    return {"count": 0, "avg": 0.0, "median": 0.0, "std": 0.0}

return {
    "count": float(values.count()),
    "avg": float(values.mean()),
    "median": float(values.median()),
    "std": float(values.std(ddof=0)),
}

-----------------------------

Sidebar

-----------------------------

st.sidebar.title("コストテーブルMVP") page = st.sidebar.radio( "画面", ["一覧", "詳細", "編集", "新規作成"], )

-----------------------------

一覧画面

-----------------------------

if page == "一覧": st.title("コストテーブル一覧")

tables_df = pd.DataFrame(get_tables())
if tables_df.empty:
    st.info("データがありません。")
else:
    filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
    with filter_col1:
        item_category_filter = st.selectbox(
            "品目分類",
            ["すべて"] + sorted(tables_df["item_category"].dropna().unique().tolist()),
        )
    with filter_col2:
        material_filter = st.selectbox(
            "材質",
            ["すべて"] + sorted(tables_df["material"].dropna().unique().tolist()),
        )
    with filter_col3:
        process_filter = st.selectbox(
            "工法",
            ["すべて"] + sorted(tables_df["process"].dropna().unique().tolist()),
        )
    with filter_col4:
        status_filter = st.selectbox(
            "ステータス",
            ["すべて"] + sorted(tables_df["status"].dropna().unique().tolist()),
        )
    with filter_col5:
        keyword = st.text_input("キーワード", placeholder="テーブル名で検索")

    filtered_df = tables_df.copy()
    if item_category_filter != "すべて":
        filtered_df = filtered_df[filtered_df["item_category"] == item_category_filter]
    if material_filter != "すべて":
        filtered_df = filtered_df[filtered_df["material"] == material_filter]
    if process_filter != "すべて":
        filtered_df = filtered_df[filtered_df["process"] == process_filter]
    if status_filter != "すべて":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]
    if keyword.strip():
        filtered_df = filtered_df[
            filtered_df["table_name"].astype(str).str.contains(keyword.strip(), case=False, na=False)
        ]

    display_columns = [
        "id",
        "table_name",
        "item_category",
        "material",
        "process",
        "supplier",
        "effective_start_date",
        "version",
        "status",
        "updated_by",
        "updated_at",
    ]
    st.dataframe(filtered_df[display_columns], use_container_width=True, hide_index=True)

    st.subheader("テーブルを開く")
    selected_id = st.selectbox(
        "対象テーブルID",
        filtered_df["id"].tolist() if not filtered_df.empty else [],
    )
    open_col, dup_col = st.columns(2)
    with open_col:
        if st.button("詳細を開く", type="primary", use_container_width=True, disabled=filtered_df.empty):
            st.session_state.selected_table_id = selected_id
            st.success(f"ID {selected_id} を選択しました。左のメニューから詳細へ進んでください。")
    with dup_col:
        if st.button("複製", use_container_width=True, disabled=filtered_df.empty):
            new_id = duplicate_table(selected_id)
            st.session_state.selected_table_id = new_id
            st.success(f"ID {selected_id} を複製して ID {new_id} を作成しました。")

-----------------------------

詳細画面

-----------------------------

elif page == "詳細": st.title("コストテーブル詳細")

table = get_table_by_id(st.session_state.selected_table_id)
if table is None:
    st.warning("対象テーブルが見つかりません。")
else:
    header_col1, header_col2, header_col3 = st.columns([3, 1, 1])
    with header_col1:
        st.subheader(table["table_name"])
    with header_col2:
        st.metric("バージョン", table["version"])
    with header_col3:
        st.metric("ステータス", table["status"])

    st.markdown("### 基本情報")
    basic_info_cols = st.columns(4)
    basic_info_cols[0].write(f"**品目分類**  \n{table['item_category']}")
    basic_info_cols[1].write(f"**材質**  \n{table['material']}")
    basic_info_cols[2].write(f"**工法**  \n{table['process']}")
    basic_info_cols[3].write(f"**サプライヤ**  \n{table['supplier']}")

    basic_info_cols2 = st.columns(3)
    basic_info_cols2[0].write(f"**適用開始日**  \n{table['effective_start_date']}")
    basic_info_cols2[1].write(f"**最終更新者**  \n{table['updated_by']}")
    basic_info_cols2[2].write(f"**最終更新日時**  \n{table['updated_at']}")

    st.write(f"**説明**  \n{table.get('description', '')}")

    st.markdown("### 明細")
    details_df = pd.DataFrame(table.get("details", []))
    st.dataframe(details_df, use_container_width=True, hide_index=True)

    st.markdown("### 根拠情報")
    summary = summarize_evidence(table)
    metric_cols = st.columns(4)
    metric_cols[0].metric("件数", int(summary["count"]))
    metric_cols[1].metric("平均単価", f"{summary['avg']:.1f}")
    metric_cols[2].metric("中央値", f"{summary['median']:.1f}")
    metric_cols[3].metric("標準偏差", f"{summary['std']:.1f}")

    evidence_df = pd.DataFrame(table.get("evidence", []))
    if evidence_df.empty:
        st.info("根拠データはまだありません。")
    else:
        st.dataframe(evidence_df, use_container_width=True, hide_index=True)

    st.markdown("### 更新履歴")
    history_df = pd.DataFrame(table.get("history", []))
    if history_df.empty:
        st.info("履歴はありません。")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("この内容を複製", use_container_width=True):
            new_id = duplicate_table(table["id"])
            st.session_state.selected_table_id = new_id
            st.success(f"複製しました。新しいIDは {new_id} です。")
    with action_col2:
        if st.button("下書きへ変更", use_container_width=True):
            table["status"] = "下書き"
            add_history_entry(table, "ステータスを下書きへ変更")
            st.success("ステータスを更新しました。")

-----------------------------

編集画面

-----------------------------

elif page == "編集": st.title("コストテーブル編集")

table = get_table_by_id(st.session_state.selected_table_id)
if table is None:
    st.warning("編集対象テーブルが見つかりません。")
else:
    with st.form("edit_form"):
        col1, col2, col3 = st.columns(3)
        table_name = col1.text_input("テーブル名", value=table.get("table_name", ""))
        item_category = col2.text_input("品目分類", value=table.get("item_category", ""))
        material = col3.text_input("材質", value=table.get("material", ""))

        col4, col5, col6 = st.columns(3)
        process = col4.text_input("工法", value=table.get("process", ""))
        supplier = col5.text_input("サプライヤ", value=table.get("supplier", ""))
        status = col6.selectbox(
            "ステータス",
            ["下書き", "承認申請", "承認済", "廃止"],
            index=["下書き", "承認申請", "承認済", "廃止"].index(table.get("status", "下書き")),
        )

        col7, col8 = st.columns(2)
        effective_start_date = col7.date_input(
            "適用開始日",
            value=pd.to_datetime(table.get("effective_start_date", date.today())).date(),
        )
        version = col8.number_input("バージョン", min_value=1, step=1, value=int(table.get("version", 1)))

        description = st.text_area("説明", value=table.get("description", ""), height=80)

        st.markdown("### 明細編集")
        source_df = pd.DataFrame(table.get("details", []))
        if source_df.empty:
            source_df = pd.DataFrame(
                [{"condition": "", "unit_price": 0, "correction_factor": 1.0, "note": ""}]
            )

        edited_df = st.data_editor(
            source_df,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "condition": st.column_config.TextColumn("condition", required=True),
                "unit_price": st.column_config.NumberColumn("unit_price", min_value=0.0, step=1.0),
                "correction_factor": st.column_config.NumberColumn(
                    "correction_factor", min_value=0.0001, step=0.01
                ),
                "note": st.column_config.TextColumn("note"),
            },
        )

        submitted = st.form_submit_button("保存", type="primary")
        if submitted:
            payload = {
                "table_name": table_name,
                "item_category": item_category,
                "material": material,
                "process": process,
                "supplier": supplier,
                "effective_start_date": effective_start_date.strftime("%Y-%m-%d"),
                "version": int(version),
                "status": status,
                "description": description,
            }
            errors = validate_table_payload(payload, edited_df)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                updated_id = create_or_update_table(table["id"], payload, edited_df)
                st.session_state.selected_table_id = updated_id
                st.success("保存しました。")

-----------------------------

新規作成画面

-----------------------------

elif page == "新規作成": st.title("コストテーブル新規作成")

with st.form("create_form"):
    col1, col2, col3 = st.columns(3)
    table_name = col1.text_input("テーブル名", value="")
    item_category = col2.text_input("品目分類", value="")
    material = col3.text_input("材質", value="")

    col4, col5, col6 = st.columns(3)
    process = col4.text_input("工法", value="")
    supplier = col5.text_input("サプライヤ", value="")
    status = col6.selectbox("ステータス", ["下書き", "承認申請", "承認済", "廃止"], index=0)

    col7, col8 = st.columns(2)
    effective_start_date = col7.date_input("適用開始日", value=date.today())
    version = col8.number_input("バージョン", min_value=1, step=1, value=1)

    description = st.text_area("説明", value="", height=80)

    st.markdown("### 明細入力")
    new_details_df = st.data_editor(
        pd.DataFrame(
            [
                {"condition": "", "unit_price": 0, "correction_factor": 1.0, "note": ""},
            ]
        ),
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "condition": st.column_config.TextColumn("condition", required=True),
            "unit_price": st.column_config.NumberColumn("unit_price", min_value=0.0, step=1.0),
            "correction_factor": st.column_config.NumberColumn(
                "correction_factor", min_value=0.0001, step=0.01
            ),
            "note": st.column_config.TextColumn("note"),
        },
    )

    create_submitted = st.form_submit_button("新規作成", type="primary")
    if create_submitted:
        payload = {
            "table_name": table_name,
            "item_category": item_category,
            "material": material,
            "process": process,
            "supplier": supplier,
            "effective_start_date": effective_start_date.strftime("%Y-%m-%d"),
            "version": int(version),
            "status": status,
            "description": description,
        }
        errors = validate_table_payload(payload, new_details_df)
        if errors:
            for err in errors:
                st.error(err)
        else:
            new_id = create_or_update_table(None, payload, new_details_df)
            st.session_state.selected_table_id = new_id
            st.success(f"新規作成しました。ID: {new_id}")

st.caption("MVP版です。次の段階では FastAPI + PostgreSQL 接続、承認フロー、差分比較、CSV入出力を追加してください。")