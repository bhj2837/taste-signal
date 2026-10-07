// 확장 쪽에서 돈다. hook.js 가 넘긴 응답을 가게별로 모아 계산하고 화면 오른쪽 아래에 작은 패널을 띄운다.
// 받은 후기는 이 탭의 메모리에만 있고 탭을 닫으면 사라진다. 저장하거나 보내지 않는다.

(async () => {
  const PATH = "/places/tab/reviews/kakaomap/";
  const shops = new Map(); // place_id -> { order, reviews: Map(review_id -> 후기), shown, hasNext }
  let core = null;
  const queue = [];

  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.source !== "taste-signal") return;
    if (core) receive(e.data);
    else queue.push(e.data);
  });
  core = await import(chrome.runtime.getURL("core.js"));
  const { REFERENCE } = await import(chrome.runtime.getURL("reference.js"));
  queue.splice(0).forEach(receive);
  window.postMessage({ source: "taste-signal-ready" }, window.location.origin);

  function receive(data) {
    let url;
    try {
      url = new URL(data.url, window.location.origin);
    } catch (err) {
      return;
    }
    const placeId = url.pathname.split(PATH)[1];
    if (!placeId) return;
    const order = url.searchParams.get("order") || "";
    const body = data.body || {};
    let shop = shops.get(placeId);
    if (!shop || shop.order !== order) {
      // 정렬을 바꾸면 처음부터 다시 모은다. 섞으면 표본이 어떤 순서로 뽑혔는지 알 수 없다
      shop = { order, reviews: new Map(), shown: null, hasNext: true };
      shops.set(placeId, shop);
    }
    for (const r of body.reviews || []) shop.reviews.set(r.review_id, core.fromApi(r));
    if (body.score_set && body.score_set.review_count != null) shop.shown = body.score_set.review_count;
    shop.hasNext = !!body.has_next;
    render(shop);
  }

  const fmt = (x) => (x > 0 ? "+" : "") + x.toFixed(2);
  const ci = (s) => `95% 구간 ${fmt(s.ci[0])} ~ ${fmt(s.ci[1])}`;

  // 구간이 0 을 걸치면 점추정이 양수든 음수든 평소와 다르다고 말할 수 없다
  function reading(st) {
    if (st.ci[0] > 0) return "평소보다 뚜렷이 후하게 받았다.";
    if (st.ci[1] < 0) return "평소보다 뚜렷이 박하게 받았다.";
    return "구간이 0을 걸쳐 있어 평소와 다르다고 말할 수 없다.";
  }

  const pctText = (x) => `${Math.max(1, Math.round(x * 100))}%`;

  function moreNeeded(s, loaded) {
    // 지금까지 펼친 후기에서 쓸 수 있는 비율로, 판단 보류를 넘으려면 몇 건이 더 필요한지 어림한다
    const rate = s.n / Math.max(loaded, 1);
    if (rate <= 0) return null;
    return Math.ceil((core.MIN_N - s.n) / rate);
  }

  let host;
  function render(shop) {
    if (!host) {
      host = document.createElement("div");
      host.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;max-width:320px";
      host.attachShadow({ mode: "open" });
      document.documentElement.appendChild(host);
    }
    const loaded = shop.reviews.size;
    const lines = [];
    const big = []; // 크게 보일 줄의 번호
    if (shop.order !== "LATEST") {
      lines.push("후기 정렬을 최신순으로 바꾸면 계산합니다.");
      lines.push("추천순은 긍정 후기를 앞에 세워서 표본이 기운다.");
    } else {
      const reviews = [...shop.reviews.values()];
      const s = core.scoreShop(reviews);
      const cate = document.querySelector(".info_cate");
      const key = core.groupOf(cate && cate.textContent, REFERENCE);
      const group = key && REFERENCE.groups[key];
      lines.push(`펼친 후기 ${loaded}건` + (shop.shown ? ` / 전체 ${shop.shown}건` : ""));
      if (!group || group.status === "pending") {
        big.push(lines.length);
        lines.push("맛 티어 없음");
        lines.push("이 업종은 아직 기준으로 삼을 가게를 모으지 않았다.");
        if (!s.taste.hold) lines.push(`맛 편차 ${fmt(s.taste.value)}  (${ci(s.taste)}, 맛 후기 ${s.taste.n}건). ` + reading(s.taste));
      } else if (group.status === "unrated") {
        big.push(lines.length);
        lines.push("맛 평가 불가");
        lines.push(`${group.reason}. 그래서 이 업종은 맛만 골라 내지 않고 전체 편차만 보여 준다.`);
        const where = core.overallInReference(s, group);
        if (where) lines.push(`전체 편차는 수집한 ${group.name} ${where.n}곳 기준 상위 ${pctText(where.top)}.`);
      } else {
        const place = core.placeInReference(s, core.expDelta(reviews), group);
        if (place) {
          big.push(lines.length);
          lines.push(`맛 티어 ${place.letter}`);
          lines.push(`수집한 ${group.name} ${place.n}곳 기준 상위 ${pctText(place.top)}.`);
          lines.push(`맛 편차 ${fmt(s.taste.value)}  (${ci(s.taste)}, 맛 후기 ${s.taste.n}건)`);
          lines.push("맛을 말한 후기에서 리뷰어가 평소보다 별을 얼마나 더 줬나. " + reading(s.taste));
          if (place.check === "lower") lines.push("후기 30개 이상 쓴 손님들은 이보다 낮게 본다.");
          else if (place.check === "higher") lines.push("후기 30개 이상 쓴 손님들은 이보다 높게 본다.");
          else if (place.check === "same") lines.push("후기 30개 이상 쓴 손님들도 같은 쪽으로 본다.");
        } else {
          big.push(lines.length);
          lines.push("맛 티어 판단 보류");
          const k = moreNeeded(s.taste, loaded);
          lines.push(`맛을 말한 후기 ${s.taste.n}건(15건 필요).` + (k && shop.hasNext ? ` 아래로 내려 약 ${k}건 더 불러오면 계산합니다.` : ""));
        }
      }
      const oneOff = core.oneOffShare(reviews);
      const top10 = group ? group.oneOffTop10 : null;
      if (oneOff != null && top10 != null && loaded >= 40 && oneOff >= top10) {
        lines.push(`후기 1개짜리 계정이 ${pctText(oneOff)}로 많다(수집한 가게 상위 10퍼센트). 판정은 아니다.`);
      }
      if (s.overall.hold) lines.push(`전체 편차(맛 외 포함)는 쓸 수 있는 후기 ${s.overall.n}건이라 보류.`);
      else lines.push(`전체 편차(맛 외 포함) ${fmt(s.overall.value)}  (${ci(s.overall)}, ${s.overall.n}건)`);
      if (s.n_ceiling) lines.push(`평소 4.8점 이상 주는 리뷰어의 후기 ${s.n_ceiling}건은 뺐다.`);
    }
    lines.push("이 화면에서 펼친 후기만으로 계산했다. 저장하거나 보내지 않는다. 맛 후기는 규칙으로 가려서 고깃집 기준 10에서 15퍼센트는 잘못 걸러진다.");
    host.shadowRoot.innerHTML =
      `<style>div{font:13px/1.5 system-ui,sans-serif;color:#111;background:#fff;border:1px solid #999;` +
      `padding:10px 12px;border-radius:6px}p{margin:0 0 4px}p.big{font-size:18px;font-weight:600;margin:4px 0}` +
      `p:last-child{margin:6px 0 0;color:#666;font-size:12px}</style>` +
      `<div>${lines.map((l, i) => `<p${big.includes(i) ? ' class="big"' : ""}>${l.replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[c])}</p>`).join("")}</div>`;
  }
})();
