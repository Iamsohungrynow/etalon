/** A WebSocket stand-in the test drives by hand: `FakeWebSocket.last.receive(...)`. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static get last(): FakeWebSocket {
    const socket = FakeWebSocket.instances.at(-1);
    if (!socket) throw new Error("no WebSocket was opened");
    return socket;
  }

  readonly url: string;
  readonly protocols: string[];
  binaryType: BinaryType = "blob";
  closed = false;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = typeof protocols === "string" ? [protocols] : (protocols ?? []);
    FakeWebSocket.instances.push(this);
  }

  receive(data: unknown): void {
    const payload = data instanceof ArrayBuffer ? data : JSON.stringify(data);
    this.onmessage?.({ data: payload } as MessageEvent);
  }

  /** The server closes the socket. */
  drop(): void {
    this.onclose?.({} as CloseEvent);
  }

  close(): void {
    this.closed = true;
  }
}
