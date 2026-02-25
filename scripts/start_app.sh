#!/usr/bin/env zsh
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR"

if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

ensure_redis() {
  if command -v redis-cli >/dev/null 2>&1; then
    if ! redis-cli ping >/dev/null 2>&1; then
      if command -v redis-server >/dev/null 2>&1; then
        echo "[redis] 启动本地 redis-server..."
        redis-server --daemonize yes
        sleep 1
      else
        echo "[redis] 未找到 redis-server，可手动启动或连接远程 Redis"
      fi
    fi
  else
    echo "[redis] 未检测到 redis-cli，若需实时管道请确保 Redis 已就绪"
  fi
}

ensure_port_free() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi

  local attempt=0
  while true; do
    local -a pids
    IFS=$'\n' pids=($(lsof -ti tcp:"$port" 2>/dev/null))
    if (( ${#pids[@]} == 0 )); then
      return
    fi

    if (( attempt == 0 )); then
      echo "[warn] 端口 $port 已被占用，尝试结束进程: ${pids[*]}"
    else
      echo "[warn] 端口 $port 仍被占用，升级处理: ${pids[*]}"
    fi

    for pid in "${pids[@]}"; do
      if (( attempt == 0 )); then
        kill "$pid" >/dev/null 2>&1 || true
      else
        kill -9 "$pid" >/dev/null 2>&1 || true
      fi
    done

    sleep 1
    (( attempt++ ))
    if (( attempt > 1 )); then
      # 两轮处理后仍占用则提示并跳出，交由 uvicorn 报错
      break
    fi
  done
}

prompt_mode() {
  echo "================ Crypto Insight 启动助手 ================"
  echo "请选择运行模式："
  echo "  1) 实时采集模式  (默认)"
  echo "     - 启动 Telegram 新闻抓取 & Redis 消费者"
  echo "     - 前端仪表盘按固定频率自动刷新"
  echo "  2) 离线分析模式"
  echo "     - 不启动实时抓取，直接读取本地 SQLite 数据"
  echo "     - 前端保持静态展示，不再自动轮询"
  read "?请输入选项 [1/2] (默认 1): " choice
  choice=${choice:-1}
  echo "$choice"
}

prompt_refresh_interval() {
  read "?设置仪表盘刷新间隔(秒，回车采用默认 60): " refresh_interval
  if [[ -z "$refresh_interval" ]]; then
    refresh_interval=60
  elif ! [[ "$refresh_interval" =~ ^[0-9]+$ ]]; then
    echo "输入非法，已恢复默认 60 秒"
    refresh_interval=60
  fi
  echo "$refresh_interval"
}

start_processes() {
  local mode_key="$1"
  local web_log="$2"
  local crawler_log="$3"

  ensure_port_free "8000"

  echo "[log] Web 前端日志: $web_log"
  if [[ -n "$crawler_log" ]]; then
    echo "[log] Crypto 新闻日志: $crawler_log"
  fi

  (uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload 2>&1 | tee -a "$web_log") &
  PIDS+=($!)

  if [[ "$mode_key" == "stream" ]]; then
    (python run_crypto_crawler.py -mode stream 2>&1 | tee -a "$crawler_log") &
    PIDS+=($!)
  fi

  wait || true
}

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" || true
    fi
  done
}

choice=$(prompt_mode)

case "$choice" in
  2)
    export ENABLE_REALTIME_PIPELINE=0
    export AUTO_REFRESH_INTERVAL=0
    echo ">> 已选择离线分析模式"
    MODE_KEY="offline"
    ;;
  1|*)
    export ENABLE_REALTIME_PIPELINE=1
    refresh=$(prompt_refresh_interval)
    export AUTO_REFRESH_INTERVAL="$refresh"
    echo ">> 已选择实时采集模式 (刷新间隔 ${refresh} 秒)"
    MODE_KEY="stream"
    ensure_redis
    ;;
esac

echo "========================================================"

export ENABLE_REALTIME_PIPELINE=${ENABLE_REALTIME_PIPELINE:-1}
export AUTO_REFRESH_INTERVAL=${AUTO_REFRESH_INTERVAL:-60}

echo "[setup] 当前 Python 版本:" "$($SHELL -lc 'python --version' 2>/dev/null || echo '未检测到')"
echo "[setup] 如需更新依赖请执行: pip install -r requirements.txt"

if [[ "$MODE_KEY" == "offline" ]]; then
  echo "[mode] 离线分析模式：禁用实时抓取，使用本地数据库"
  echo "[ui] 仪表盘自动刷新已关闭"
else
  echo "[mode] 实时采集模式：启动抓取并推送数据"
  if [[ "$AUTO_REFRESH_INTERVAL" == "0" ]]; then
    echo "[ui] 仪表盘自动刷新已关闭"
  else
    echo "[ui] 仪表盘将每 ${AUTO_REFRESH_INTERVAL} 秒刷新一次"
  fi
fi

timestamp=$(date +"%Y%m%d-%H%M%S")
web_log="$LOG_DIR/web_app_${MODE_KEY}_${timestamp}.log"
crawler_log=""
if [[ "$MODE_KEY" == "stream" ]]; then
  crawler_log="$LOG_DIR/crypto_crawler_${timestamp}.log"
fi

typeset -a PIDS=()
trap cleanup INT TERM EXIT

start_processes "$MODE_KEY" "$web_log" "$crawler_log"
