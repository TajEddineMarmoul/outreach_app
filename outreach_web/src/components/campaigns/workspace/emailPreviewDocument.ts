/** Isolate email HTML from the app and prevent previews from loading trackers. */
export function emailPreviewDocument(body: string): string {
  return `<!doctype html><html><head><meta name="color-scheme" content="light"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'"><style>body{margin:0;padding:20px 0;font:15px/1.65 Arial,sans-serif;color:#16213b;overflow-wrap:anywhere}p{margin:0 0 20px}a{color:#0751f8}ul,ol{padding-left:24px}img{max-width:100%}</style></head><body>${body}</body></html>`;
}
