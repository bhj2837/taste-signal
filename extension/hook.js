// 페이지 쪽에서 돈다(world: MAIN). 페이지가 스스로 부른 후기 응답을 복사해 panel.js 로 넘긴다.
// 요청을 새로 만들거나 바꾸지 않는다. 다음 페이지를 부르는 것은 사용자가 「더보기」 를 눌렀을 때 페이지가 한다.

(() => {
  const PATH = "/places/tab/reviews/kakaomap/";
  // panel.js 는 문서가 다 뜬 뒤에 시작해서 첫 응답을 놓칠 수 있다. 받은 것을 쌓아 두고, 패널이 준비됐다고 알리면 다시 보낸다
  const sent = [];
  const post = (msg) => {
    try {
      window.postMessage(msg, window.location.origin);
    } catch (e) {
      // 넘기지 못해도 페이지 동작에는 손대지 않는다
    }
  };
  const send = (url, body) => {
    const msg = { source: "taste-signal", url: String(url), body };
    sent.push(msg);
    post(msg);
  };
  window.addEventListener("message", (e) => {
    if (e.source === window && e.data && e.data.source === "taste-signal-ready") sent.forEach(post);
  });

  const origFetch = window.fetch;
  window.fetch = function (...args) {
    const p = origFetch.apply(this, args);
    const url = args[0] && args[0].url ? args[0].url : args[0];
    if (String(url).includes(PATH)) {
      p.then((res) => res.clone().json().then((body) => send(res.url || url, body))).catch(() => {});
    }
    return p;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (String(url).includes(PATH)) {
      this.addEventListener("load", () => {
        try {
          const body = this.responseType === "json" ? this.response : JSON.parse(this.responseText);
          send(this.responseURL || url, body);
        } catch (e) {
          // 형식이 다르면 무시한다
        }
      });
    }
    return origOpen.call(this, method, url, ...rest);
  };
})();
