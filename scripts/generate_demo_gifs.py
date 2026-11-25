#!/usr/bin/env python3
"""Generate animated GIF demos for README.md and docs/TUTORIAL.md.

Produces:
  - docs/assets/merapy-cli-demo.gif
  - docs/assets/taskqueue-dashboard-demo.gif
  - docs/assets/standalone-taskqueue-demo.gif
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from merapy_taskqueue import JobRecord, JobStatus, MemoryJobStore, TaskContext, TaskQueue
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "docs" / "assets"
CHROME_BIN = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FONT_MONO_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_SANS_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Terminal renderer (macOS dark window)
# ---------------------------------------------------------------------------

BG_CANVAS = (13, 17, 23)
BG_WINDOW = (22, 27, 34)
BG_TITLEBAR = (33, 38, 45)
BORDER_COLOR = (48, 54, 61)

COLORS = {
    "default": (230, 237, 243),
    "dim": (139, 148, 158),
    "prompt": (88, 166, 255),
    "cmd": (255, 255, 255),
    "green": (63, 185, 80),
    "yellow": (210, 153, 34),
    "cyan": (121, 192, 255),
    "purple": (210, 168, 255),
    "accent": (129, 140, 248),
}

LineSpec = tuple[str, str]  # (text, color_key)


def render_terminal_frame(
    title: str,
    lines: list[LineSpec],
    *,
    width: int = 920,
    height: int = 540,
    show_cursor: bool = False,
) -> Image.Image:
    img = Image.new("RGB", (width, height), BG_CANVAS)
    draw = ImageDraw.Draw(img)

    pad = 16
    win_box = [pad, pad, width - pad, height - pad]
    draw.rounded_rectangle(win_box, radius=14, fill=BG_WINDOW, outline=BORDER_COLOR, width=2)

    # Title bar
    bar_h = 38
    draw.rounded_rectangle(
        [pad, pad, width - pad, pad + bar_h],
        radius=14,
        fill=BG_TITLEBAR,
    )
    draw.rectangle([pad + 1, pad + bar_h - 14, width - pad - 1, pad + bar_h], fill=BG_TITLEBAR)
    draw.line([pad, pad + bar_h, width - pad, pad + bar_h], fill=BORDER_COLOR, width=1)

    # Traffic light dots
    dot_y = pad + bar_h // 2
    for idx, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        cx = pad + 20 + idx * 20
        draw.ellipse([cx - 6, dot_y - 6, cx + 6, dot_y + 6], fill=col)

    font_title = _load_font(FONT_MONO_PATH, 13)
    tb = draw.textbbox((0, 0), title, font=font_title)
    tw = tb[2] - tb[0]
    draw.text(((width - tw) // 2, pad + 11), title, fill=COLORS["dim"], font=font_title)

    # Terminal lines
    font = _load_font(FONT_MONO_PATH, 15)
    line_h = 22
    max_lines = (height - pad * 2 - bar_h - 28) // line_h
    visible = lines[-max_lines:]

    x0 = pad + 22
    y = pad + bar_h + 18
    for text, color_key in visible:
        color = COLORS.get(color_key, COLORS["default"])
        draw.text((x0, y), text, fill=color, font=font)
        y += line_h

    if show_cursor and visible:
        last_text = visible[-1][0]
        bb = draw.textbbox((0, 0), last_text, font=font)
        cx = x0 + (bb[2] - bb[0]) + 3
        cy = y - line_h + 2
        draw.rectangle([cx, cy, cx + 9, cy + 16], fill=COLORS["accent"])

    return img


def save_gif(frames: list[Image.Image], durations_ms: list[int], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    paletted = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for f in frames]
    paletted[0].save(
        out_path,
        save_all=True,
        append_images=paletted[1:],
        duration=durations_ms,
        loop=0,
        optimize=True,
    )
    size_kb = out_path.stat().st_size / 1024
    print(f"Created {out_path} ({len(frames)} frames, {size_kb:.1f} KB)")


def _type_command(
    title: str,
    history: list[LineSpec],
    prompt: str,
    command: str,
    frames: list[Image.Image],
    durations: list[int],
) -> None:
    step = max(2, len(command) // 10)
    for end in range(step, len(command) + 1, step):
        typed = command[:end]
        frames.append(render_terminal_frame(title, [*history, (f"{prompt}{typed}", "cmd")], show_cursor=True))
        durations.append(75)
    if len(command) % step != 0:
        frames.append(render_terminal_frame(title, [*history, (f"{prompt}{command}", "cmd")], show_cursor=True))
        durations.append(90)
    history.append((f"{prompt}{command}", "cmd"))
    frames.append(render_terminal_frame(title, history, show_cursor=False))
    durations.append(260)


def generate_cli_demo_gif() -> None:  # noqa: PLR0915
    """Capture real CLI scaffold output and animate it into docs/assets/merapy-cli-demo.gif."""
    # Run the real CLI in a temp dir to verify exact output
    bin_path = ROOT / "release" / "merapy-macos-arm64"
    cli_cmd = [str(bin_path)] if bin_path.is_file() else [sys.executable, "-m", "merapy.cli"]

    with tempfile.TemporaryDirectory(prefix="merapy-gif-") as tmp:
        tmp_path = Path(tmp)
        ver = subprocess.run([*cli_cmd, "--version"], capture_output=True, text=True, check=True)
        version_line = ver.stdout.strip()

        init_proc = subprocess.run(
            [*cli_cmd, "init"],
            input="order-service\norder\n1,3\n6\n2\n",
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
        )
        svc_dir = tmp_path / "order-service"
        mod_proc = subprocess.run(
            [*cli_cmd, "add-module", "payment"],
            cwd=str(svc_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        hdl_proc = subprocess.run(
            [*cli_cmd, "add-handler", "order", "cron"],
            cwd=str(svc_dir),
            capture_output=True,
            text=True,
            check=True,
        )

        # Extract summary lines from real CLI outputs
        init_summary = [ln for ln in init_proc.stdout.splitlines() if ln.strip().startswith(("✓", "modules", "servers", "workers", "deps", "files"))]
        mod_summary = [ln for ln in mod_proc.stdout.splitlines() if ln.strip().startswith("✓")]
        hdl_summary = [ln for ln in hdl_proc.stdout.splitlines() if ln.strip().startswith("✓")]

    title = "merapy — CLI Scaffolder Demo"
    history: list[LineSpec] = []
    frames: list[Image.Image] = []
    durations: list[int] = []

    # 1. Version
    _type_command(title, history, "$ ", "merapy --version", frames, durations)
    history.append((version_line, "cyan"))
    frames.append(render_terminal_frame(title, history))
    durations.append(750)

    # 2. Interactive init
    _type_command(title, history, "$ ", "merapy init", frames, durations)
    prompts = [
        ("Please input service name", ">> order-service"),
        ("Please input new module names (comma separated)", ">> order"),
        ("Select server handlers: 1) REST  2) gRPC  3) GraphQL", ">> 1,3"),
        ("Select worker handlers: ... 6) Task Queue", ">> 6"),
        ("Select dependencies: 1) Redis  2) SQL  3) Mongo", ">> 2"),
    ]
    for question, answer in prompts:
        history.append((question, "dim"))
        frames.append(render_terminal_frame(title, history))
        durations.append(300)
        history.append((answer, "yellow"))
        frames.append(render_terminal_frame(title, history))
        durations.append(350)

    for ln in init_summary:
        color = "green" if "✓" in ln else "cyan"
        clean = ln.replace(str(tmp_path.resolve()) + "/", "./").replace(str(tmp_path) + "/", "./")
        history.append((clean, color))
    frames.append(render_terminal_frame(title, history))
    durations.append(1500)

    # 3. Add module
    _type_command(title, history, "$ ", "cd order-service && merapy add-module payment", frames, durations)
    for ln in mod_summary or ["✓ module 'payment' added and wired via @merapy markers"]:
        history.append((ln, "green"))
    frames.append(render_terminal_frame(title, history))
    durations.append(1100)

    # 4. Add handler
    _type_command(title, history, "$ ", "merapy add-handler order cron", frames, durations)
    for ln in hdl_summary or ["✓ cron handler wired into module 'order'"]:
        history.append((ln, "green"))
    frames.append(render_terminal_frame(title, history))
    durations.append(1200)

    # 5. Start hint
    history.append(("", "default"))
    history.append(("# Start REST (:8000), GraphQL (:8100), & Task Queue Dashboard (:8080):", "dim"))
    _type_command(title, history, "$ ", "make migration && make run", frames, durations)
    history.append(("✓ REST server listening on http://localhost:8000", "green"))
    history.append(("✓ Task Queue Dashboard live at http://localhost:8080", "purple"))
    frames.append(render_terminal_frame(title, history))
    durations.append(2400)

    save_gif(frames, durations, ASSETS_DIR / "merapy-cli-demo.gif")


def generate_standalone_taskqueue_gif() -> None:
    """Create a crisp terminal GIF demonstrating standalone merapy-taskqueue usage."""
    title = "merapy-taskqueue — Use in Any Python Project"
    history: list[LineSpec] = []
    frames: list[Image.Image] = []
    durations: list[int] = []

    _type_command(title, history, "$ ", "pip install merapy-taskqueue", frames, durations)
    history.append(("Successfully installed merapy-taskqueue-0.1.0 (53 KB wheel + embedded UI)", "green"))
    frames.append(render_terminal_frame(title, history))
    durations.append(900)

    _type_command(title, history, "$ ", "cat app.py", frames, durations)
    code_lines: list[LineSpec] = [
        ("import asyncio", "purple"),
        ("from merapy_taskqueue import MemoryJobStore, TaskContext, TaskQueue", "purple"),
        ("", "default"),
        ("tq = TaskQueue(store=MemoryJobStore(), service_name='billing-app')", "cyan"),
        ("", "default"),
        ("@tq.task('send_email')", "yellow"),
        ("async def send_email(ctx: TaskContext):", "cyan"),
        ("    return {'sent': True, 'job': ctx.job_id}", "default"),
        ("", "default"),
        ("async def main():", "cyan"),
        ("    await tq.enqueue('send_email', {'to': 'alice@example.com'})", "default"),
        ("    await tq.serve()  # worker + live Vite/Preact dashboard on :8080", "green"),
        ("", "default"),
        ("asyncio.run(main())", "default"),
    ]
    for ln in code_lines:
        history.append(ln)
    frames.append(render_terminal_frame(title, history))
    durations.append(2000)

    _type_command(title, history, "$ ", "python app.py", frames, durations)
    history.append(("INFO  task_queue.started  tasks=['send_email']  store=MemoryJobStore", "cyan"))
    history.append(("INFO  dashboard.ready     url=http://localhost:8080  (23 KB gzipped UI)", "purple"))
    history.append(("INFO  job.completed       task=send_email  status=SUCCESS  retries=1/5", "green"))
    frames.append(render_terminal_frame(title, history))
    durations.append(2500)

    save_gif(frames, durations, ASSETS_DIR / "standalone-taskqueue-demo.gif")


# ---------------------------------------------------------------------------
# Live Dashboard GIF (real headless Chrome captures against live server)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _chrome_screenshot(url: str, out_png: Path, *, dark: bool = False) -> None:
    cmd = [
        str(CHROME_BIN),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--window-size=1280,820",
        "--virtual-time-budget=3500",
        f"--screenshot={out_png}",
    ]
    if dark:
        cmd.append("--force-dark-mode")
    cmd.append(url)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _frame_with_caption(img_path: Path, step_label: str, caption: str) -> Image.Image:
    raw = Image.open(img_path).convert("RGB")
    target_w = 1040
    scale = target_w / raw.width
    resized = raw.resize((target_w, int(raw.height * scale)), Image.Resampling.LANCZOS)

    banner_h = 46
    canvas = Image.new("RGB", (target_w, resized.height + banner_h), (15, 23, 42))
    draw = ImageDraw.Draw(canvas)

    font_pill = _load_font(FONT_SANS_PATH, 13)
    font_cap = _load_font(FONT_MONO_PATH, 14)

    # Step pill (Framed Sheet teal accent)
    draw.rounded_rectangle([16, 10, 128, 36], radius=13, fill=(27, 108, 128))
    draw.text((28, 15), step_label, fill=(255, 255, 255), font=font_pill)
    draw.text((144, 15), caption, fill=(226, 232, 240), font=font_cap)

    canvas.paste(resized, (0, banner_h))
    return canvas


def generate_dashboard_demo_gif() -> None:  # noqa: PLR0915
    """Spin up a live merapy_taskqueue dashboard, capture real Chrome frames, and shut down."""
    if not CHROME_BIN.is_file():
        print("Skipping Chrome dashboard capture: Google Chrome not found")
        return

    port = _free_port()
    store = MemoryJobStore()
    tq = TaskQueue(
        store=store,
        dashboard_enabled=False,
        service_name="order-service",
        service_version="1.4.2",
        framework_version="0.1.0",
        build_number="142",
        git_commit="1793183",
        build_date="2026-11-25T18:00:00Z",
    )

    @tq.task("send_email", module_name="notification")
    async def send_email(ctx: TaskContext) -> dict[str, object]:
        payload = json.loads(ctx.arguments)
        return {"delivered": True, "recipient": payload.get("to")}

    @tq.task("generate_invoice", module_name="billing")
    async def generate_invoice(ctx: TaskContext) -> dict[str, object]:
        payload = json.loads(ctx.arguments)
        return {"pdf_url": f"https://cdn.example.com/inv-{payload.get('order_id')}.pdf"}

    @tq.task("sync_inventory", module_name="warehouse")
    async def sync_inventory(ctx: TaskContext) -> dict[str, object]:
        del ctx
        return {"synced": 24}

    async def seed_initial() -> tuple[str, str]:
        # Pre-populate realistic mix of statuses
        success_job = JobRecord(
            task_name="send_email",
            arguments=json.dumps({"to": "alice@example.com", "template": "order_confirmed", "order_id": 1042}),
            retries=1,
            max_retry=3,
            status=JobStatus.SUCCESS,
            result=json.dumps({"delivered": True, "message_id": "msg_9f2a1c"}),
            trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        )
        await store.enqueue(success_job)

        failed_job = JobRecord(
            task_name="send_email",
            arguments=json.dumps({"to": "bounce@invalid.test", "template": "receipt", "order_id": 1041}),
            retries=3,
            max_retry=3,
            status=JobStatus.FAILURE,
            error="SMTPConnectionError: 421 temporary rate limit exceeded",
            trace_id="7df12a8819c44aa0b8ee102f3a1b9912",
        )
        await store.enqueue(failed_job)

        await store.enqueue(
            JobRecord(
                task_name="send_email",
                arguments=json.dumps({"to": "bob@example.com", "template": "shipping_update", "order_id": 1043}),
                retries=0,
                max_retry=3,
                status=JobStatus.QUEUEING,
            )
        )
        await store.enqueue(
            JobRecord(
                task_name="generate_invoice",
                arguments=json.dumps({"order_id": 1042, "currency": "USD", "amount": 149.0}),
                retries=1,
                max_retry=3,
                status=JobStatus.SUCCESS,
                result=json.dumps({"pdf_url": "https://cdn.example.com/inv-1042.pdf"}),
            )
        )
        await store.enqueue(
            JobRecord(
                task_name="generate_invoice",
                arguments=json.dumps({"order_id": 1044, "currency": "USD", "amount": 89.5}),
                retries=0,
                max_retry=3,
                status=JobStatus.RETRYING,
            )
        )
        await store.enqueue(
            JobRecord(
                task_name="sync_inventory",
                arguments=json.dumps({"warehouse": "ap-southeast-1", "sku_batch": 12}),
                retries=1,
                max_retry=5,
                status=JobStatus.STOPPED,
            )
        )
        return success_job.id, failed_job.id

    loop = asyncio.new_event_loop()
    success_id, failed_id = loop.run_until_complete(seed_initial())

    app = tq.dashboard_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="on")
    server = uvicorn.Server(config)

    def _run_server() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    # Wait until listening
    for _ in range(40):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)

    base = f"http://127.0.0.1:{port}"
    frames: list[Image.Image] = []
    durations: list[int] = []

    try:
        with tempfile.TemporaryDirectory(prefix="merapy-dash-shots-") as tmp:
            tdir = Path(tmp)

            # Frame 1: Dashboard Overview (initial state)
            p1 = tdir / "01_overview.png"
            _chrome_screenshot(f"{base}/", p1)
            frames.append(_frame_with_caption(p1, "STEP 1 / 5", "Live Overview — Status cards, Deployment & Runtime metrics, Task table"))
            durations.append(2400)

            # Execute queued jobs live so frame 2 shows real-time transition!
            fut = asyncio.run_coroutine_threadsafe(tq.tick(), loop)
            fut.result(timeout=5)
            time.sleep(0.3)

            # Frame 2: Dashboard Overview after live execution
            p2 = tdir / "02_overview_updated.png"
            _chrome_screenshot(f"{base}/", p2)
            frames.append(_frame_with_caption(p2, "STEP 2 / 5", "Real-Time Update — Queued job executed automatically via GraphQL subscription"))
            durations.append(2200)

            # Frame 3: Task detail job table
            p3 = tdir / "03_task.png"
            _chrome_screenshot(f"{base}/task?task_name=send_email", p3)
            frames.append(_frame_with_caption(p3, "STEP 3 / 5", "Task Jobs (/task) — Filter by status, search args, Retry / Stop / Clear"))
            durations.append(2400)

            # Frame 4: Job detail view (failed job showing error + Retry button)
            p4 = tdir / "04_job_failed.png"
            _chrome_screenshot(f"{base}/job?id={failed_id}", p4)
            frames.append(_frame_with_caption(p4, "STEP 4 / 5", "Job Inspector (/job) — Arguments, error trace, and one-click Retry / Delete"))
            durations.append(2400)

            # Frame 5: Job detail view (succeeded job showing result + Trace ID)
            p5 = tdir / "05_job_success.png"
            _chrome_screenshot(f"{base}/job?id={success_id}", p5)
            frames.append(_frame_with_caption(p5, "STEP 5 / 5", "Completed Job — Pretty JSON arguments, result payload, and OpenTelemetry Trace ID"))
            durations.append(2600)

        save_gif(frames, durations, ASSETS_DIR / "taskqueue-dashboard-demo.gif")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def main() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    generate_cli_demo_gif()
    generate_standalone_taskqueue_gif()
    generate_dashboard_demo_gif()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
