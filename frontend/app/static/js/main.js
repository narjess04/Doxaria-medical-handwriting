// MediTrust — interactions de l'interface (sans dépendance).
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;

  // Menu mobile
  const toggle = document.querySelector(".nav-toggle");
  const menu = document.getElementById("menu");
  toggle?.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    menu.classList.toggle("open", open);
  });
  menu?.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => {
    toggle?.setAttribute("aria-expanded", "false");
    menu.classList.remove("open");
  }));

  // Afficher / masquer le mot de passe
  document.querySelectorAll(".toggle-password").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.target);
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      btn.setAttribute("aria-label", visible ? "Afficher le mot de passe" : "Masquer le mot de passe");
    });
  });

  // Confirmation avant suppression
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => { if (!confirm(form.dataset.confirm)) e.preventDefault(); });
  });

  // Copier le texte extrait
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const source = document.querySelector(btn.dataset.copy);
      try {
        await navigator.clipboard.writeText(source.value ?? source.textContent);
        const old = btn.innerHTML;
        btn.textContent = "Copié !";
        setTimeout(() => { btn.innerHTML = old; }, 1500);
      } catch { source.select?.(); }
    });
  });

  // Import d'image : ordinateur, galerie ou appareil photo.
  // Le fichier retenu est toujours envoyé sous le nom « image ».
  document.querySelectorAll("form[data-upload]").forEach((form) => {
    const inputs = [...form.querySelectorAll('input[type="file"]')];
    const zone = form.querySelector("[data-dropzone]");
    const empty = zone.querySelector(".dropzone-empty");
    const previewBox = zone.querySelector(".dropzone-preview");
    const preview = form.querySelector("[data-preview]");
    const nameEl = form.querySelector("[data-name]");
    const submit = form.querySelector("[data-submit]");
    const verdict = form.querySelector("[data-verdict]");
    const types = ["image/jpeg", "image/png", "image/webp"];
    let courant = null;

    const choisir = (input) => {
      const file = input.files?.[0];
      if (!file) return;
      inputs.forEach((i) => { if (i !== input) { i.removeAttribute("name"); i.value = ""; } });
      input.name = "image";
      courant = file;
      if (preview.src.startsWith("blob:")) URL.revokeObjectURL(preview.src);
      preview.src = URL.createObjectURL(file);
      nameEl.textContent = `${file.name} · ${(file.size / 1048576).toFixed(1)} Mo`;
      empty.hidden = true;
      previewBox.hidden = false;
      submit.disabled = false;
      if (verdict) verdict.hidden = true;
    };
    inputs.forEach((i) => i.addEventListener("change", () => choisir(i)));

    form.querySelector("[data-reset]").addEventListener("click", () => {
      inputs.forEach((i) => { i.value = ""; i.removeAttribute("name"); });
      inputs[0].name = "image";
      courant = null;
      empty.hidden = false;
      previewBox.hidden = true;
      submit.disabled = true;
      if (verdict) verdict.hidden = true;
    });

    ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("drag"); }));
    ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("drag"); }));
    zone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files?.[0];
      if (!file) return;
      if (!types.includes(file.type)) { alert("Format non pris en charge : choisissez une image JPG, PNG ou WebP."); return; }
      const dt = new DataTransfer();
      dt.items.add(file);
      inputs[0].files = dt.files;
      choisir(inputs[0]);
    });

    form.addEventListener("submit", async (e) => {
      if (!courant) { e.preventDefault(); return; }
      if (courant.size > 10 * 1048576) { e.preventDefault(); alert("Image trop volumineuse (10 Mo maximum)."); return; }
      submit.classList.add("loading");
      submit.disabled = true;
      if (!form.dataset.fraude) return; // envoi classique du formulaire

      e.preventDefault();
      const data = new FormData();
      data.append("image", courant);
      try {
        const r = await fetch(form.dataset.fraude, { method: "POST", body: data, headers: { "X-CSRFToken": csrf } });
        const res = await r.json();
        afficherVerdict(verdict, r.ok ? res : { erreur: res.erreur || "Analyse impossible." });
      } catch {
        afficherVerdict(verdict, { erreur: "Le serveur ne répond pas. Réessayez." });
      } finally {
        submit.classList.remove("loading");
        submit.disabled = false;
      }
    });
  });

  function afficherVerdict(box, res) {
    box.hidden = false;
    box.replaceChildren();
    const ok = !res.erreur && res.verdict === "conforme";
    box.className = `verdict ${ok ? "ok" : "ko"}`;
    const icon = document.createElement("span");
    icon.className = "verdict-icon";
    icon.innerHTML = ok
      ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>'
      : '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>';
    const body = document.createElement("div");
    const h = document.createElement("h3");
    const p = document.createElement("p");
    if (res.erreur) {
      h.textContent = "Erreur";
      p.textContent = res.erreur;
    } else {
      h.textContent = ok ? "Document conforme" : "Document suspect";
      p.textContent = res.message;
    }
    body.append(h, p);
    if (res.details) {
      const pct = (v) => `${Math.round(v * 100)} %`;
      const d = res.details;
      const ul = document.createElement("ul");
      ul.className = "verdict-details";
      [
        ["Cachet", d.cachet != null ? `détecté (confiance ${pct(d.cachet)})` : "non détecté"],
        ["En-tête du médecin", d.entete_medecin != null ? `détecté (confiance ${pct(d.entete_medecin)})` : "non détecté"],
        ["Nom du cachet / en-tête", d.correspondance != null ? `${pct(d.correspondance)} des mots retrouvés` : "non comparé"],
      ].forEach(([k, v]) => {
        const li = document.createElement("li");
        const b = document.createElement("b");
        b.textContent = `${k} : `;
        li.append(b, v);
        ul.append(li);
      });
      body.append(ul);
    }
    if (res.demo) {
      const b = document.createElement("span");
      b.className = "badge badge-demo";
      b.textContent = "Mode démonstration : exemple de résultat, le modèle n'est pas encore branché";
      body.append(b);
    }
    box.append(icon, body);
  }

  // Assistant médical
  const chat = document.querySelector("[data-chat]");
  if (chat) {
    const log = chat.querySelector("[data-log]");
    const form = chat.querySelector("[data-form]");
    const input = form.querySelector("textarea");
    const avatar = log.querySelector(".msg-avatar img")?.src;

    const el = (tag, cls, text) => {
      const n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text != null) n.textContent = text;
      return n;
    };
    const bulle = (role) => {
      const msg = el("div", `msg msg-${role}`);
      if (role === "bot") {
        const a = el("span", "msg-avatar");
        const img = el("img");
        img.src = avatar; img.alt = ""; img.width = 22; img.height = 24;
        a.append(img);
        msg.append(a);
      }
      const body = el("div", "msg-body");
      msg.append(body);
      log.append(msg);
      log.scrollTop = log.scrollHeight;
      return body;
    };

    // Markdown du modèle de langage, assaini avant insertion (aucun HTML exécutable).
    const markdown = (texte) => {
      const div = el("div", "md");
      if (window.marked && window.DOMPurify) {
        div.innerHTML = DOMPurify.sanitize(marked.parse(texte, { breaks: true }));
        div.querySelectorAll("a").forEach((a) => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
      } else {
        texte.split(/\n{2,}/).forEach((p) => div.append(el("p", null, p)));
      }
      return div;
    };

    const historique = [];

    const reponse = (body, r) => {
      body.replaceChildren();
      if (r.markdown) body.append(markdown(r.markdown));
      if (r.titre) body.append(el("p", "msg-title", r.titre));
      if (r.fiche) {
        const dl = el("dl", "msg-fiche");
        r.fiche.forEach(([k, v]) => { const d = el("div"); d.append(el("dt", null, k), el("dd", null, v)); dl.append(d); });
        body.append(dl);
      }
      if (r.texte) body.append(el("p", null, r.texte));
      if (r.source) body.append(el("p", "msg-source", `Source : ${r.source}`));
      if (r.suggestions) {
        const s = el("div", "suggestions");
        r.suggestions.forEach((t) => { const c = el("button", "chip", t); c.type = "button"; c.dataset.suggestion = ""; s.append(c); });
        body.append(s);
      }
      log.scrollTop = log.scrollHeight;
    };

    const bouton = form.querySelector("button");
    let enCours = false;

    const envoyer = async (question) => {
      question = question.trim();
      if (!question || enCours) return;
      enCours = true;
      bouton.disabled = true;
      bulle("user").append(el("p", null, question));
      input.value = "";
      ajuster();
      const body = bulle("bot");
      body.innerHTML = '<span class="typing" aria-label="L\'assistant écrit"><span></span><span></span><span></span></span>';
      try {
        const r = await fetch(chat.dataset.chat, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify({ question, historique: historique.slice(-8) }),
        });
        const res = await r.json();
        reponse(body, res);
        historique.push({ role: "user", content: question });
        historique.push({ role: "assistant", content: res.markdown || res.texte || "" });
      } catch {
        reponse(body, { texte: "Le serveur ne répond pas. Réessayez." });
      } finally {
        enCours = false;
        bouton.disabled = false;
        input.focus();
      }
    };

    // Zone de saisie qui s'agrandit ; Entrée envoie, Maj+Entrée va à la ligne.
    const ajuster = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 160)}px`; };
    input.addEventListener("input", ajuster);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); envoyer(input.value); }
    });
    form.addEventListener("submit", (e) => { e.preventDefault(); envoyer(input.value); });
    log.addEventListener("click", (e) => {
      if (e.target.matches("[data-suggestion]")) envoyer(e.target.textContent);
    });
    document.querySelector("[data-reset-chat]")?.addEventListener("click", () => {
      historique.length = 0;
      log.querySelectorAll(".msg:not([data-accueil])").forEach((m) => m.remove());
      input.focus();
    });
    // Question transmise par une autre page (« Analyser avec l'assistant »),
    // envoyée une fois les bibliothèques Markdown chargées.
    if (chat.dataset.question) window.addEventListener("load", () => envoyer(chat.dataset.question));
  }
})();
