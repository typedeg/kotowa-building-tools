# 建築法規チェックツール

建築士向けの建築基準法チェックツール（Streamlit アプリ）。

## ツール一覧

### 既存住宅 法規チェック（building_code_checker）

既存住宅の建築基準法適合性を自動判定します。

- 耐震基準・建ぺい率・容積率・接道義務・省エネ・基礎・防火・用途・居住性能など11項目
- Markdown レポートのダウンロード機能付き

**起動方法（ローカル）:**
```bash
pip install -r building_code_checker/requirements.txt
python3 -m streamlit run building_code_checker/streamlit_app.py
```

---

### 新築計画 法規チェック（madori_generator）

新築計画の法規適合性を自動チェックします。

- 建蔽率・容積率・道路斜線・省エネ基準（R7年4月義務化）など
- 推奨建物規模・建物寸法の算出

**起動方法（ローカル）:**
```bash
pip install -r madori_generator/requirements.txt
python3 -m streamlit run madori_generator/streamlit_app.py
```
