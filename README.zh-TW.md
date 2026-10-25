<div align="center">

[简体中文](README.md) | **繁體中文** | [English](README.en.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<img src="https://raw.githubusercontent.com/ErisPulse/ErisPulse/main/.github/assets/ErisPulseLogo.png" width="180" alt="QvQChat" />

</div>

# QvQChat

**ErisPulse 的通用 agent 模組：在你的機器人所在的平台上聊天、呼叫工具、寫程式並執行、安排排程任務、維護長期記憶。**

QvQChat 的核心是一個工具迴圈。接上模型之後，模型可以透過任意 ErisPulse 平台轉接器（adapter）收發訊息、呼叫其他已安裝模組的服務、讀寫檔案、執行 shell 命令與 Python 程式、建立排程任務，並把值得記住的東西存進長期記憶。任何時刻有哪些工具可用，只取決於你裝了什麼；模組安裝與移除都不需要重啟。

它是寫給已經在跑 ErisPulse 機器人、希望機器人真正去做事而不只是回話的人。你往模型池裡填任意 OpenAI 相容的端點，決定誰可以使用哪些工具，之後每裝一個生態模組，agent 就多一批能力。

模組需要 ErisPulse 2.8.0 以上版本，以及至少一個平台轉接器。它內建一個網頁控制台，脫離 Dashboard 也能獨立運作；聊天端與網頁端走同一條管線，從 QQ 發起的任務會即時出現在瀏覽器裡，也可以在瀏覽器裡直接停掉。

<p>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/pypi/v/ErisPulse-QvQChat?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/wsu2059q/ErisPulse-QvQChat/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/pkgs/container/erispulse-qvqchat"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
</p>

<img src=".github/assets/overview.png" width="860" alt="QvQChat 網頁控制台" />

---

## 安裝

用 ErisPulse CLI：

```bash
epsdk install ErisPulse-QvQChat
```

或用 pip（需要 Python 3.10+、ErisPulse >= 2.8.0，並至少安裝一個平台轉接器）：

```bash
pip install ErisPulse-QvQChat
```

或用 Docker。映像檔以 ErisPulse 官方映像為基礎建置，已內建本模組：

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

## 快速開始

1. 安裝模組與至少一個轉接器，例如 `epsdk install ErisPulse-OneBotAdapter`。
2. 開啟 Dashboard，進入 QvQChat 視窗。在模型池頁面新增一個 OpenAI 相容模型：名稱、Base URL、API Key、模型名稱四項就夠了。
3. 告訴 agent 誰是管理員。`admins` 為空時聊天端沒有人擁有管理員權限，執行命令這類工具在聊天端就無法使用：

```toml
[QvQChat]
admins = ["123456"]   # 你在聊天平台上的使用者 id
```

4. 開啟 `http://<host>:8000/QvQChat/view` 進入獨立控制台，或直接使用 Dashboard 側邊欄的 QvQChat 入口。有安裝 Dashboard 時沿用它的登入權杖；沒有時 QvQChat 會在首次啟動自動產生存取權杖並印到日誌，你也可以自行設定 `QvQChat.view_token`。
5. 私訊機器人，或在群組裡 @ 它。它在你的使用者已經在的地方回答。

聊天命令的主命令是 `/qvq`（`/agent` 保留為相容別名，各子命令也接受英文寫法）：

| 命令 | 作用 |
|---|---|
| `/qvq` | 查看命令說明 |
| `/qvq 重置` | 重置目前會話的對話 |
| `/qvq 人格 [id]` | 查看或切換人格 |
| `/qvq 開場` | 重送目前人格的開場白（管理員） |
| `/qvq 任務` | 查看排程任務 |
| `/qvq 記憶` | 查看記憶、事實與使用者畫像，管理員可分級清空 |
| `/qvq 壓縮` | 立即壓縮目前會話的上下文 |
| `/qvq 狀態` | 模型、工具與會話概況 |
| `/qvq 接管 [分鐘]` | 接管目前會話（管理員），預設 10 分鐘 |
| `/qvq 釋放` | 釋放接管 |

---

## agent 能做什麼

### 帶著一整套實用工具的工具迴圈

內建工具涵蓋訊息收發（`send_message`、`send_dsl`）、平台 API、檔案存取、shell 與 Python 執行、長期記憶、知識庫、排程任務與人格。`run_python_sdk` 在主程序內行 Python，腳本可以直接使用 sdk、轉接器與 storage。`spawn_agent` 會為值得單獨探索的任務派出一個獨立會話的子 agent，只把結論帶回主對話。同一個工具連續失敗兩次時，會注入一條附錯誤摘要的修正提示，讓模型自行調整參數重試（`tool_self_heal`，預設開啟）。

工具還有另外兩個來源：你連線的每個 MCP 伺服器都會貢獻自己的工具（支援 stdio 與 Streamable HTTP）；裝了宣告 `services` 的 ErisPulse 模組，它的服務也會被自動呼叫。見下文[擴充 QvQChat](#擴充-qvqchat)。

完成一次新的多步任務後，你可以要求模型把做法保存為技能。技能就是 `data/QvQChat/skills` 下的 Markdown 檔案，需要時注入系統提示；`skill_induct` 可以整個關掉這個機制。

### 網頁控制台

<img src=".github/assets/chat.png" width="49%" alt="對話頁" /> <img src=".github/assets/models.png" width="49%" alt="模型池頁" />

`/QvQChat/view` 的對話頁串流輸出回覆，每個工具呼叫在時間軸上各占一步，模型的思考過程以摺疊區塊呈現。這裡有給想晚點再送的訊息用的暫存佇列，也有停止執行中任務的按鈕。重新整理頁面或過一會再回來，跑到的任務會從原處接上。會話可以置頂、封存、改名，新的會話由模型自動命名。任何會話都能產生臨時唯讀分享連結，可設定到期時間與 token 預算，也能匯出為 Markdown。

控制台同時承載管理頁面：模型池、人格、知識庫、稽核記錄、任務執行記錄與成本估算。設定頁以合適的控制項呈現每個設定項，附帶校驗與未儲存提示。需要程式化接入時，還有 OpenAI 相容端點 `GET /v1/models` 與 `POST /v1/chat/completions`（含串流），以同一組存取權杖做 Bearer 認證。

因為兩側共用同一條管線，agent 在聊天平台發起的任務會逐個工具呼叫地即時出現在瀏覽器裡，而且可以在那邊停掉。

### 群組與人格

群組裡被 @ 時 agent 醒來，可以設定喚醒前綴，私訊預設觸發。純對話的回覆按段落切開逐條傳送，節奏可調、接近真人；工具任務的結果在平台支援時打包成合併轉發卡片。開啟 `reply_narrate` 後，agent 執行工具任務時會像工作播報一樣邊做邊說：動手前說一句要做什麼，每個結果簡短回報，最後給一句結論，每句話單獨送到群裡。

人格攜帶系統提示、開場白、語氣參數與示例對話，還可以限定可用的工具子集。群組成員可以有成員級人格，逐級回退到群組級與全域人格。`group_isolation` 則讓群組裡每位成員擁有獨立的上下文、人格與記憶，適合更在意隔離的群組。在群組裡不被 @ 也主動插話這件事，核心刻意沒做：它交給參與決策外掛判斷，並且在你開啟 `participation_enabled` 之前保持關閉（見下方 QvQStalker）。

<img src=".github/assets/qq.png" width="680" alt="agent 在 QQ 群組裡工作" />

### 記憶、使用者畫像與知識庫

agent 以會話為單位維護長期記憶，另有全域範圍，每次請求注入相關的幾條，也可以透過工具讓它記住或忘記某件事。偏好、約定這類事實會從對話中自動抽取，之後注入回來。在此之上，同一使用者在各會話的事實與記憶會定期（預設每 6 小時）固化為跨會話畫像；30 天內沒有任何新事實強化的畫像項目會自動淘汰。`/qvq 記憶` 與控制台的記憶頁可以查看存了什麼，也能按類別清空。

知識庫存放較長的文件。條目分塊後依詞面計分檢索，相關片段自動注入系統提示。條目也可以像 SillyTavern 世界書那樣設定觸發關鍵字，只有聊到相關內容時才注入對應設定。如果設定了 OpenAI 相容的 embedding 端點，檢索會切換為餘弦相似度，鏈路上任何一環無法使用時自動回退詞面檢索。

### 會自我照料的模型池

模型放在按供應商組織的池子裡，任意 OpenAI 相容端點都能用，常用廠商有預設，新增只是一張短表單。模型條目會從 models.dev 目錄自動補上能力位元（視覺、檔案、工具呼叫、推理）與價格，兩者都可以手動覆寫。請求失敗時沿池子順序容錯移轉，連續失敗三次的模型進入指數退避的冷卻期，容錯移轉鏈會跳過缺少所需能力的模型。主模型不會看圖時，由視覺模型代為描述再把文字交給它。難度感知路由可以把寒暄分給便宜模型、程式碼與長分析分給強模型，屬於實驗特性，預設關閉。用量按模型按日記錄並提供成本估算，摘要、下標題這類背景工作可以透過 `task_models` 指定給更便宜的模型。如果你願意（`self_config`，預設開啟），agent 甚至能透過僅管理員可用的工具自己管理模型池、MCP 伺服器與設定。

### 撐得住長任務的上下文

舊的工具輸出會持續瘦身。估算的上下文規模超過門檻時（CJK 口徑估算，預設 128000），舊輪次被摘要成一段早期上下文摘要而不是直接丟棄；壓縮也可以每 N 輪預防性執行，或用 `/qvq 壓縮` 手動觸發。可選的預算模式按優先順序把系統提示的各部件與歷史裝進所選模型的上下文視窗，溢出時觸發壓縮，壓縮的同時還會把實體、偏好與待辦抽取為事實。工具預算給得很寬（預設 50 輪、150 次呼叫），接近上限時模型收到的是收斂提醒，而不是被硬生生掐斷。

### 重啟也撐得住的排程任務

排程任務由 agent 自己透過工具以自然語言建立。支援四種格式：`cron:0 9 * * 1-5`、`at:2026-10-17 09:00`、`in:30m`、`every:2h`。標記為深度的任務按三段執行：計畫、執行、審查，審查發現缺口時自動做一輪有界修正。任務的執行記錄會落盤，可在控制台查看。有安裝 ErisPulse-Cron 時 cron 任務交給它託管。程序在生成中途重啟的話，被中斷的回覆會被識別並重跑，傳送失敗佇列在啟動時重放，中斷的任務執行記錄也會被標記（`recovery_enabled` 及相關設定）。

### 安全模型

電腦操作分三個等級。`strict` 不執行任何命令與程式碼，只允許白名單目錄內的唯讀檔案操作。`standard`（預設）下危險命令要在聊天裡確認後才執行，確認提示會附上命令全文，檔案存取限制在 `work_dirs` 內。`permissive` 解除限制，改為把所有操作記入稽核日誌。工具分為所有人可用的基礎安全集（傳訊息、記憶、唯讀檔案、排程任務）與管理員專用（執行、寫檔案、子 agent、轉接器與模組呼叫）。排程任務以建立者的權限執行。`admins` 決定誰是管理員，`safe_tools` 可以把指定工具開放給所有人，`owner_only` 把整個 agent 限制為主人使用，`trust_agent` 跳過確認但仍然全部稽核。

---

## 配套外掛

有兩個獨立模組擴充了 QvQChat，也順帶展示了擴充點能做什麼：

- [ErisPulse-QvQStalker](https://github.com/wsu2059q/ErisPulse-QvQStalker)：讓 agent 透過旁聽通道關注群組對話，自己判斷什麼時候該插話。熱度追蹤、五層判定與衝動值共同決定它何時開口，15 項行為參數透過 `qvq_settings` 註冊，在設定頁裡直接調整。
- [ErisPulse-QvQMemes](https://github.com/wsu2059q/ErisPulse-QvQMemes)：給 agent 一個貼圖習慣。`send_sticker` 工具讓模型自己挑當下該發哪張，群組裡的圖片經旁聽通道自動收錄並由視覺模型打標籤，新鮮度降權讓它不至於翻來覆去就那幾張。

在你開啟 `participation_enabled` 之前，群組參與始終是關閉的；裝外掛本身不會打開這道門。

## 擴充 QvQChat

擴充就是普通的 ErisPulse 模組，不需要任何專屬介面。模組在 `get_meta()` 裡宣告 `services`，每個服務就自動成為 agent 的工具，裝上即生效、移除即消失：

```python
from ErisPulse.Core.Bases import BaseModule, ModuleMeta

class Main(BaseModule):
    @staticmethod
    def get_meta() -> ModuleMeta:
        return ModuleMeta(name="Draw", services=[
            {"name": "draw", "description": "依描述生成圖片，回傳圖片 URL"},
        ])

    async def draw(self, prompt: str, size: str = "1024x1024"):
        return {"image_url": "https://..."}
```

想整合得更深，模組可以實作以下約定服務中的任意幾個，生態橋會發現它們並在模組安裝與移除時熱重新整理：

- `qvq_personas()` 回傳人格預設（id、名稱、系統提示，可選的工具子集）；
- `qvq_schemas()` 為本模組的服務回傳顯式 JSON Schema，覆蓋簽名推斷；
- `qvq_settings()` 宣告設定描述符，設定頁會呈現它們，值經 `plugin_config` 服務與 `qvq.plugin_config` 事件回流到外掛。

模組也可以訂閱 `qvq.message`、`qvq.replied` 這類生命週期事件。反過來，QvQChat 自己宣告了 `chat`、`run_prompt`、`get_status` 三個服務供其他模組呼叫。完整的約定，包括附件處理與權限模型，見 [docs/inter-module.md](docs/inter-module.md)（簡體中文）。

## 設定

所有設定都在 `QvQChat` 節之下，可以在 Dashboard 設定頁裡修改，按模型、觸發、對話、工具、生態、MCP、記憶、知識庫、技能、任務、用量、安全、參與、存取分組。本頁提到的每個鍵，從 `wake_prefixes`、`user_rate_limit` 到 `daily_token_limit`、`delivery_profiles`，都是那裡一個附說明的普通設定項。最近的變更見 [CHANGELOG.md](CHANGELOG.md)，模組的內部結構見 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 開發

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat
cd ErisPulse-QvQChat
pip install -e .[test]
pytest
```

## 授權條款

[MIT](LICENSE)
