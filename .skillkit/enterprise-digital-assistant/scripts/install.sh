#!/usr/bin/env bash
# ============================================================
# 企业数字助理 · 电脑端安装脚本
# 方式A：把本技能安装到 WorkBuddy（用户级 ~/.workbuddy/skills）
# 方式B：把 eda 装进 PATH（~/local/bin），并生成双击启动器
# ============================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"          # 技能包根目录
SKILL_NAME="enterprise-digital-assistant"
SKILLS_DIR="${HOME}/.workbuddy/skills"
BIN_DIR="${HOME}/local/bin"

echo "== 企业数字助理 安装 =="

# ---- A. 安装到 WorkBuddy 技能库 ----
echo "[1/3] 安装到 WorkBuddy 技能库: ${SKILLS_DIR}/${SKILL_NAME}"
if [ "${HERE}" = "${SKILLS_DIR}/${SKILL_NAME}" ]; then
  echo "     已在技能库内（跳过拷贝）"
else
  mkdir -p "${SKILLS_DIR}"
  if [ -d "${SKILLS_DIR}/${SKILL_NAME}" ]; then
    echo "     已存在同名技能，覆盖更新…"
    rm -rf "${SKILLS_DIR}/${SKILL_NAME}"
  fi
  cp -R "${HERE}" "${SKILLS_DIR}/${SKILL_NAME}"
  chmod +x "${SKILLS_DIR}/${SKILL_NAME}/scripts/eda.py"
  echo "     ✓ 完成（重启 WorkBuddy / 新会话即生效）"
fi

# ---- B. eda 进 PATH ----
echo "[2/3] 安装 eda 命令到: ${BIN_DIR}"
mkdir -p "${BIN_DIR}"
rm -f "${BIN_DIR}/eda"
if ln -s "${SKILLS_DIR}/${SKILL_NAME}/scripts/eda.py" "${BIN_DIR}/eda" 2>/dev/null; then
  echo "     ✓ 完成（软链）"
else
  cp "${SKILLS_DIR}/${SKILL_NAME}/scripts/eda.py" "${BIN_DIR}/eda" && chmod +x "${BIN_DIR}/eda"
  echo "     ✓ 完成（复制模式，因软链不可用）"
fi

# ---- C. 双击启动器（源码包与已安装技能各一份） ----
echo "[3/3] 生成启动器: 企业数字助理.command"
for target_dir in "${HERE}" "${SKILLS_DIR}/${SKILL_NAME}"; do
cat > "${target_dir}/企业数字助理.command" <<'LAUNCH'
#!/usr/bin/env bash
clear
echo "======================================"
echo "   企业数字助理 · 交互菜单"
echo "======================================"
echo " 1) 制度问答（如：报销怎么走流程）"
echo " 2) 查员工（如：李华）"
echo " 3) 入职培训"
echo " 4) 发企业微信（stub 演示）"
echo " q) 退出"
echo "======================================"
read -r -p "选择: " choice
case "$choice" in
  1) read -r -p "问题: " q; python3 "$(dirname "$0")/scripts/eda.py" ask "$q" ;;
  2) read -r -p "姓名: " n; python3 "$(dirname "$0")/scripts/eda.py" find "$n" ;;
  3) read -r -p "新员工姓名: " n; python3 "$(dirname "$0")/scripts/eda.py" onboard --name "$n" ;;
  4) read -r -p "收件人: " n; read -r -p "内容: " c; python3 "$(dirname "$0")/scripts/eda.py" send "$n" "$c" ;;
  *) exit 0 ;;
esac
LAUNCH
chmod +x "${target_dir}/企业数字助理.command"
done
echo "     ✓ 完成"

echo
echo "== 安装完成 =="
echo " • 技能方式：WorkBuddy 对话中直接说「企业数字助理…」「给张伟发消息…」即可触发"
echo " • CLI 方式：${BIN_DIR}/eda（已加入下面命令即可用）"
echo " • 启动器：  ${HERE}/企业数字助理.command（双击运行交互菜单）"
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
  echo " • 提示：把 ${BIN_DIR} 加入 PATH：echo 'export PATH=\"\${HOME}/local/bin:\${PATH}\"' >> ~/.zshrc"
fi
