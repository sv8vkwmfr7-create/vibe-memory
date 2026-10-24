"""Read-only native ZCode metadata probe; no inference or credential extraction."""
import json
from pathlib import Path
import queue
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / 'results/zcode_automation_probe_v1'
NODE = 'C:/Program Files/nodejs/node.exe'
CLI = 'C:/Users/ASYS/AppData/Roaming/npm/node_modules/zcode-app-cli/bin/zcode.js'


def request(method, params, *, diagnostics=None):
    if diagnostics is not None:
        diagnostics.update(client_requests=[], raw_error_omitted=True)
    child = subprocess.Popen([NODE, CLI, 'app-server'], cwd=WORKSPACE,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    responses = queue.Queue()
    def read():
        for line in child.stdout:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if diagnostics is not None and 'method' in value and 'id' in value:
                known = {'session/requestRuntimePreferences',
                         'interaction/requestProviderRuntimeHeaders',
                         'interaction/requestOfficialMcpAuthHeaders',
                         'interaction/requestPermission', 'interaction/requestUserInput'}
                name = value['method'] if isinstance(value['method'], str) and value['method'] in known else 'other'
                if len(diagnostics['client_requests']) < 32:
                    diagnostics['client_requests'].append(dict(
                        method=name, action='answered' if name == 'session/requestRuntimePreferences' else 'denied'))
            if value.get('method') == 'session/requestRuntimePreferences' and 'id' in value:
                child.stdin.write(json.dumps(dict(id=value['id'], result=dict(
                    nativeSearchEnhancementsEnabled=False, memoryEnabled=False,
                    askUserQuestionAutoResolutionEnabled=False))) + '\n')
                child.stdin.flush()
                continue
            if 'method' in value and 'id' in value:
                child.stdin.write(json.dumps(dict(id=value['id'], error=dict(
                    code=-32601, message='Probe denies unsupported client requests'))) + '\n')
                child.stdin.flush()
                continue
            if value.get('id') == 1:
                if diagnostics is not None and isinstance(value.get('error'), dict):
                    error = value['error']
                    code = error.get('code')
                    code = code if type(code) is int else None
                    diagnostics['error_code'] = code
                    diagnostics['error_category'] = {
                        -32600: 'invalid_request', -32601: 'method_not_found',
                        -32602: 'invalid_params', -32603: 'internal_error',
                    }.get(code, 'other_error')
                    # Fixed hints only: never copy vendor text, URLs, headers or data.
                    message = error.get('message')
                    message = message.lower()[:8192] if isinstance(message, str) else ''
                    diagnostics['message_hints'] = [label for label, terms in (
                        ('output_limit', ('maxoutputtokens', 'max_output_tokens', 'max_tokens')),
                        ('provider_headers', ('runtime headers', 'runtimeheaders')),
                        ('authentication', ('unauthorized', 'authentication failed')),
                        ('quota', ('quota exceeded', 'insufficient balance')),
                        ('timeout', ('timed out', 'timeout')),
                    ) if any(term in message for term in terms)]
                responses.put(value)
                return
    threading.Thread(target=read, daemon=True).start()
    try:
        child.stdin.write(json.dumps(dict(id=1, method=method, params=params)) + '\n')
        child.stdin.flush()
        try:
            return responses.get(timeout=40)
        except queue.Empty:
            if diagnostics is not None:
                diagnostics['error_category'] = 'local_response_timeout'
            raise
    finally:
        child.stdin.close()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def summarize(value, path=''):
    # Whitelist metadata only; never serialize raw provider/account payloads.
    if isinstance(value, dict):
        for key, item in value.items():
            current = path + '/' + key
            if key in {'apiKey', 'headers', 'credentials', 'token', 'accessToken', 'refreshToken'}:
                continue
            if key in {'id', 'providerId', 'modelId', 'mode', 'entitled', 'authMode'} and isinstance(item, (str, bool)):
                if isinstance(item, bool) or any(s in str(item).lower() for s in ['glm', 'account:', 'start-plan', 'coding-plan', 'standalone', 'host']):
                    print(json.dumps(dict(path=current, value=item)))
            elif isinstance(item, (dict, list)):
                summarize(item, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            summarize(item, path + '/' + str(index))


if __name__ == '__main__':
    assert WORKSPACE.is_dir()
    workspace = dict(workspaceKey=str(WORKSPACE), workspacePath=str(WORKSPACE))
    for method, params in [('runtime/capabilities', {}),
                           ('workspace/readPresentation', dict(workspace=workspace))]:
        result = request(method, params)
        print(json.dumps(dict(method=method, has_result='result' in result,
                             result_keys=list(result.get('result', {})),
                             error_code=result.get('error', {}).get('code'))))
        summarize(result.get('result', {}))
