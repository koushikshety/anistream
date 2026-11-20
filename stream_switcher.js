/**
 * AniStream Multi-Server & Official "Where to Watch" Switcher
 * Loads episodes.json (embeddable YouTube sources) + watch_links.json (licensed external platforms)
 */
(function () {
  async function loadJson(path) {
    try {
      const res = await fetch(path + "?v=" + Math.floor(Date.now() / 60000));
      if (!res.ok) return null;
      return await res.json();
    } catch (_) {
      return null;
    }
  }

  function normalizeTitle(str) {
    return (str || "")
      .toLowerCase()
      .replace(/\[.*?\]|\(.*?\)/g, "")
      .replace(/episode\s*\d+|ep\.?\s*\d+/gi, "")
      .replace(/[^a-z0-9]+/g, " ")
      .trim();
  }

  window.initAniStreamSwitcher = async function ({
    title,
    episode = 1,
    playerContainerId = "player-stage",
    serverBarId = "server-switcher-bar",
  }) {
    const playerEl = document.getElementById(playerContainerId);
    const barEl = document.getElementById(serverBarId);
    if (!playerEl || !barEl) return;

    const [ytEpisodes, watchData] = await Promise.all([
      loadJson("./episodes.json"),
      loadJson("./watch_links.json"),
    ]);

    const targetNorm = normalizeTitle(title);

    // 1. Collect all matching official YouTube servers for this title & episode
    const embedServers = (ytEpisodes || []).filter((item) => {
      const itemNorm = normalizeTitle(item.title);
      const titleMatch =
        itemNorm.includes(targetNorm) || targetNorm.includes(itemNorm);
      const epMatch =
        Number(item.episode) === Number(episode) ||
        (Number(episode) >= Number(item.episode) &&
          Number(episode) <= Number(item.last_episode || item.episode));
      return titleMatch && epMatch;
    });

    // 2. Collect all official external platform links (Bilibili, iQIYI, WeTV, Viki, Crunchyroll, etc.)
    const watchEntry = (watchData?.items || []).find((m) => {
      const mNorm = normalizeTitle(m.title);
      return mNorm === targetNorm || mNorm.includes(targetNorm) || targetNorm.includes(mNorm);
    });
    const externalServers = watchEntry?.where_to_watch || [];

    barEl.innerHTML = "";

    function selectEmbedServer(server, btn) {
      barEl.querySelectorAll(".srv-btn").forEach((b) => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      playerEl.innerHTML = `
        <iframe
          src="${server.embed_url}?autoplay=1&rel=0"
          title="${server.title}"
          style="width:100%;height:100%;border:0;aspect-ratio:16/9;"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowfullscreen>
        </iframe>
      `;
    }

    // Render Embeddable YouTube Server Buttons
    embedServers.forEach((srv, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "srv-btn" + (idx === 0 ? " active" : "");
      btn.textContent = `▶ ${srv.channel} (HD)`;
      btn.onclick = () => selectEmbedServer(srv, btn);
      barEl.appendChild(btn);
    });

    // Render Official External Platform Links (Link-out only, no broken/illegal iframes)
    externalServers.forEach((ext) => {
      const a = document.createElement("a");
      a.href = ext.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.className = "srv-btn srv-ext";
      a.textContent = `↗ Watch on ${ext.platform}`;
      barEl.appendChild(a);
    });

    // Auto-load first working YouTube embed, or show official Where-to-Watch card
    if (embedServers.length > 0) {
      selectEmbedServer(embedServers[0], barEl.querySelector(".srv-btn"));
    } else if (externalServers.length > 0) {
      playerEl.innerHTML = `
        <div style="padding:24px;text-align:center;color:#fff;background:#111;border-radius:10px;">
          <p style="margin-bottom:12px;">Direct YouTube embed is not available in your region for this episode. Watch officially on:</p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            ${externalServers
              .map(
                (s) =>
                  `<a href="${s.url}" target="_blank" rel="noopener noreferrer" style="padding:10px 16px;background:#e50914;color:#fff;border-radius:6px;text-decoration:none;font-weight:600;">Watch on ${s.platform}</a>`
              )
              .join("")}
          </div>
        </div>
      `;
    }
  };
})();
