const API_BASE = '';

export async function fetchAPI(path: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });
    if (!res.ok) {
        throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return res.json();
}

export function connectWebSocket(onMessage: (data: any) => void) {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage(data);
    };
    ws.onerror = (err) => console.error('WebSocket error:', err);
    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting in 5s...');
        setTimeout(() => connectWebSocket(onMessage), 5000);
    };
    return ws;
}
