import httpx

URL = "http://localhost:11400/chat"

def main():
    payload = {"query": "¿Cómo constituyo una empresa en Chile?"}
    print(f"POST {URL} -> payload: {payload}")
    try:
        with httpx.stream("POST", URL, json=payload, timeout=None) as resp:
            print("Status:", resp.status_code)
            if resp.status_code != 200:
                text = resp.content.decode(errors='ignore')
                print("Error response:", text)
                return
            print("Streaming response (raw chunks):")
            for chunk in resp.iter_bytes():
                if not chunk:
                    continue
                try:
                    s = chunk.decode('utf-8')
                except Exception:
                    s = chunk.decode('latin-1', errors='ignore')
                print(s, end='', flush=True)
    except Exception as e:
        print('Request failed:', e)

if __name__ == '__main__':
    main()
