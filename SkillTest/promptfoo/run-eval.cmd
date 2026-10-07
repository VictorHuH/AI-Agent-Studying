@echo off
rem run-eval.cmd - run promptfoo skill eval with Ark gateway auth
rem Auth token comes from the Windows user env var OPENAI_API_KEY (set once via: setx OPENAI_API_KEY <key>).
rem Windows user env vars are inherited by the SDK subprocess promptfoo spawns.
rem NOTE: keep this file ASCII-only. cmd.exe on zh-CN Windows reads it as GBK,
rem and UTF-8 Chinese comments corrupt the following line (learned the hard way).
set ANTHROPIC_BASE_URL=https://ark.cn-beijing.volces.com/api/coding
set ANTHROPIC_AUTH_TOKEN=%OPENAI_API_KEY%
set ANTHROPIC_MODEL=glm-5.3[1M]
cd /d "%~dp0"
npx promptfoo eval %*
