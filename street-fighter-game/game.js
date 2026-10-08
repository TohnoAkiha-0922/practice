const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const playerHealthEl = document.getElementById("playerHealth");
const enemyHealthEl = document.getElementById("enemyHealth");
const playerEnergyEl = document.getElementById("playerEnergy");
const enemyEnergyEl = document.getElementById("enemyEnergy");
const timerText = document.getElementById("timerText");
const banner = document.getElementById("banner");
const bannerTitle = document.getElementById("bannerTitle");
const bannerText = document.getElementById("bannerText");
const restartBtn = document.getElementById("restartBtn");

const keys = new Set();
const baseGround = 385;
const assetRoot = "assets/streets_of_fight/Streets of Fight files";
const stagePreview = loadImage(`${assetRoot}/Previews/Stage/preview_stage.png`);
const shadowImage = loadImage(`${assetRoot}/Sprites/shadow.png`);
const sprites = {
  player: {
    defaultFacing: 1,
    idle: frames("Brawler-Girl/Idle/idle", 4),
    walk: frames("Brawler-Girl/Walk/walk", 10),
    jab: frames("Brawler-Girl/Jab/jab", 3),
    punch: frames("Brawler-Girl/Punch/punch", 3),
    jump: frames("Brawler-Girl/Jump/jump", 4),
    hurt: frames("Brawler-Girl/Hurt/hurt", 2),
  },
  enemy: {
    defaultFacing: -1,
    idle: frames("Enemy-Punk/Idle/idle", 4),
    walk: frames("Enemy-Punk/Walk/walk", 4),
    punch: frames("Enemy-Punk/Punch/punch", 3),
    hurt: frames("Enemy-Punk/Hurt/hurt", 4),
  },
};
const skillDefs = {
  dash: { cost: 18, cooldown: 0.9, damage: 14, label: "Dash" },
  wave: { cost: 26, cooldown: 1.15, damage: 12, label: "Wave" },
  ult: { cost: 100, cooldown: 5.2, damage: 34, label: "Ult" },
};
const attackDefs = {
  normal: { cooldown: 0.34, timer: 0.24, damage: 8, reach: 58, knock: 210 },
  heavy: { cooldown: 0.62, timer: 0.42, damage: 16, reach: 76, knock: 360 },
};

let last = 0;
let matchOver = false;
let timeLeft = 90;
let shake = 0;
let particles = [];
let projectiles = [];
let flashes = [];

function loadImage(src) {
  const image = new Image();
  image.src = src;
  return image;
}

function frames(prefix, count) {
  const images = [];
  for (let i = 1; i <= count; i += 1) {
    images.push(loadImage(`${assetRoot}/Sprites/${prefix}${i}.png`));
  }
  return images;
}

function renderScaleX(f) {
  const defaultFacing = sprites[f.name]?.defaultFacing || 1;
  return f.facing === defaultFacing ? 1 : -1;
}

const player = makeFighter({
  name: "player",
  x: 230,
  color: "#2d8f67",
  trim: "#f3b13a",
  facing: 1,
});

const enemy = makeFighter({
  name: "enemy",
  x: 720,
  color: "#c83b2b",
  trim: "#246f8f",
  facing: -1,
});

function makeFighter(config) {
  return {
    ...config,
    lane: 0,
    jump: 0,
    vx: 0,
    vlane: 0,
    vjump: 0,
    width: 56,
    height: 136,
    health: 100,
    energy: 35,
    hitStun: 0,
    attack: null,
    attackCd: 0,
    block: false,
    grounded: true,
    skillCd: { dash: 0, wave: 0, ult: 0 },
    aiThink: 0,
    retreatTimer: 0,
    animState: "idle",
    animChangedAt: 0,
  };
}

function resetGame() {
  Object.assign(player, makeFighter({ name: "player", x: 230, color: "#2d8f67", trim: "#f3b13a", facing: 1 }));
  Object.assign(enemy, makeFighter({ name: "enemy", x: 720, color: "#c83b2b", trim: "#246f8f", facing: -1 }));
  particles = [];
  projectiles = [];
  flashes = [];
  matchOver = false;
  timeLeft = 90;
  shake = 0;
  banner.classList.add("hidden");
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function footY(f) {
  return baseGround + f.lane - f.jump;
}

function bodyRect(f) {
  return { x: f.x - f.width / 2, y: footY(f) - f.height, w: f.width, h: f.height };
}

function rectsOverlap(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function laneClose(a, b, range = 42) {
  return Math.abs(a.lane - b.lane) <= range;
}

function canUse(f, skill) {
  return !matchOver && f.hitStun <= 0 && f.skillCd[skill] <= 0 && f.energy >= skillDefs[skill].cost;
}

function spendSkill(f, skill) {
  f.energy -= skillDefs[skill].cost;
  f.skillCd[skill] = skillDefs[skill].cooldown;
}

function startAttack(f, kind) {
  if (matchOver || f.hitStun > 0 || f.attackCd > 0 || f.attack) return;
  const def = attackDefs[kind];
  f.attack = { kind, timer: def.timer, damage: def.damage, reach: def.reach, knock: def.knock, hasHit: false };
  f.attackCd = def.cooldown;
  f.animState = kind === "normal" ? "jab" : "punch";
  f.animChangedAt = performance.now();
}

function useDash(f) {
  if (!canUse(f, "dash")) return;
  spendSkill(f, "dash");
  f.attack = { kind: "dash", timer: 0.22, damage: skillDefs.dash.damage, reach: 86, knock: 380, hasHit: false };
  f.animState = "punch";
  f.animChangedAt = performance.now();
  f.vx = f.facing * 720;
  burst(f.x, footY(f) - 74, f.trim, 14);
}

function useWave(f) {
  if (!canUse(f, "wave")) return;
  spendSkill(f, "wave");
  projectiles.push({
    owner: f.name,
    x: f.x + f.facing * 42,
    lane: f.lane,
    y: footY(f) - 90,
    vx: f.facing * 520,
    radius: 16,
    damage: skillDefs.wave.damage,
    life: 1.45,
    color: f.trim,
  });
  burst(f.x + f.facing * 36, footY(f) - 90, f.trim, 10);
}

function useUltimate(f, target) {
  if (!canUse(f, "ult")) return;
  spendSkill(f, "ult");
  flashes.push({ x: f.x, y: footY(f) - 90, radius: 12, life: 0.45, color: f.trim });
  shake = 18;
  if (Math.abs(target.x - f.x) < 250 && laneClose(f, target, 70)) {
    damageFighter(f, target, skillDefs.ult.damage, 520);
  }
  for (let i = 0; i < 42; i += 1) {
    burst(f.x + (Math.random() - 0.5) * 260, footY(f) - 90 + (Math.random() - 0.5) * 120, f.trim, 1);
  }
}

function jump(f) {
  if (!matchOver && f.grounded && f.hitStun <= 0) {
    f.vjump = 660;
    f.grounded = false;
  }
}

function updateFighter(f, other, dt) {
  f.hitStun = Math.max(0, f.hitStun - dt);
  f.attackCd = Math.max(0, f.attackCd - dt);
  f.block = false;
  Object.keys(f.skillCd).forEach((key) => {
    f.skillCd[key] = Math.max(0, f.skillCd[key] - dt);
  });
  f.energy = clamp(f.energy + dt * (f.block ? 5 : 9), 0, 100);

  if (f.attack) {
    f.attack.timer -= dt;
    if (f.attack.timer <= 0) f.attack = null;
  }

  if (f.hitStun <= 0 && !matchOver) {
    if (f.name === "player") updatePlayerMovement(f);
    else enemyBrain(f, other, dt);
  }

  f.jump += f.vjump * dt;
  f.vjump -= 1650 * dt;
  if (f.jump <= 0) {
    f.jump = 0;
    f.vjump = 0;
    f.grounded = true;
  }

  f.x = clamp(f.x + f.vx * dt, 52, canvas.width - 52);
  f.lane = clamp(f.lane + f.vlane * dt, -72, 70);
  f.vx *= 0.78;
  f.vlane *= 0.72;
  f.facing = other.x > f.x ? 1 : -1;
}

function updatePlayerMovement(f) {
  const left = keys.has("a");
  const right = keys.has("d");
  const up = keys.has("w");
  const down = keys.has("s");
  f.vx += ((right ? 1 : 0) - (left ? 1 : 0)) * 42;
  f.vlane += ((down ? 1 : 0) - (up ? 1 : 0)) * 34;
  f.block = keys.has("l") && f.grounded && !f.attack;
  if (f.block) {
    f.vx *= 0.56;
    f.vlane *= 0.56;
  }
  f.vx = clamp(f.vx, -280, 280);
  f.vlane = clamp(f.vlane, -210, 210);
}

function enemyBrain(f, other, dt) {
  const distance = Math.abs(other.x - f.x);
  const sameLane = laneClose(f, other, 42);
  const direction = Math.sign(other.x - f.x) || f.facing;
  f.aiThink -= dt;
  f.retreatTimer = Math.max(0, f.retreatTimer - dt);

  if (f.retreatTimer > 0 || (sameLane && distance < 58)) {
    f.vx -= direction * 42;
    if (sameLane) f.vlane += (f.lane <= other.lane ? -1 : 1) * 26;
  } else if (distance > 150) {
    f.vx += direction * 24;
  } else if (distance < 92 && sameLane) {
    f.vx -= direction * 18;
  } else {
    f.vx += Math.sin(performance.now() / 360) * 4;
  }
  f.vlane += Math.sign(other.lane - f.lane) * (sameLane ? 5 : 16);
  f.vx = clamp(f.vx, -190, 190);
  f.vlane = clamp(f.vlane, -135, 135);

  if (f.aiThink <= 0) {
    f.aiThink = 0.45 + Math.random() * 0.55;
    f.block = distance < 96 && other.attack && sameLane && Math.random() < 0.55;
    if (f.block) return;
    if (distance < 82 && sameLane) {
      startAttack(f, Math.random() < 0.68 ? "normal" : "heavy");
      f.retreatTimer = 0.45 + Math.random() * 0.35;
    } else if (distance > 115 && distance < 360 && laneClose(f, other, 48) && Math.random() < 0.78) {
      useWave(f);
    } else if (distance > 95 && distance < 145 && sameLane && Math.random() < 0.28) {
      useDash(f);
      f.retreatTimer = 0.55;
    }
    else if (f.energy >= 100 && distance < 260 && Math.random() < 0.55) useUltimate(f, other);
  }
}

function resolveMelee(attacker, defender) {
  if (!attacker.attack || attacker.attack.hasHit || attacker.attack.timer <= 0) return;
  const reach = attacker.attack.reach;
  const hit = {
    x: attacker.facing > 0 ? attacker.x + 12 : attacker.x - reach - 12,
    y: footY(attacker) - 112,
    w: reach,
    h: 58,
  };
  if (!laneClose(attacker, defender, 42) || !rectsOverlap(hit, bodyRect(defender))) return;
  attacker.attack.hasHit = true;
  damageFighter(attacker, defender, attacker.attack.damage, attacker.attack.knock);
}

function damageFighter(attacker, defender, damage, knock) {
  const defenderFacingAttacker = Math.sign(attacker.x - defender.x) === defender.facing;
  const blocked = defender.block && defenderFacingAttacker && laneClose(attacker, defender, 50);
  const finalDamage = blocked ? Math.max(2, Math.ceil(damage * 0.25)) : damage;
  defender.health = clamp(defender.health - finalDamage, 0, 100);
  defender.hitStun = blocked ? 0.08 : 0.28;
  defender.animState = blocked ? "idle" : "hurt";
  defender.animChangedAt = performance.now();
  if (attacker.name === "enemy") attacker.retreatTimer = Math.max(attacker.retreatTimer, 0.45);
  defender.vx = attacker.facing * (blocked ? knock * 0.22 : knock);
  if (!blocked) {
    defender.vjump = Math.max(defender.vjump, 170);
    defender.grounded = false;
  }
  shake = Math.max(shake, blocked ? 4 : damage > 20 ? 14 : 8);
  burst(defender.x - defender.facing * 18, footY(defender) - 86, blocked ? "#7cc7e8" : attacker.trim, blocked ? 9 : damage > 20 ? 26 : 16);
  if (defender.health <= 0) {
    endMatch(attacker.name === "player" ? "\u80dc\u5229" : "\u5931\u8d25", attacker.name === "player" ? "\u4f60\u7528\u6280\u80fd\u6253\u8d62\u4e86\u5bf9\u624b" : "\u5bf9\u624b\u51fb\u8d25\u4e86\u4f60");
  }
}

function updateProjectiles(dt) {
  projectiles.forEach((p) => {
    p.x += p.vx * dt;
    p.life -= dt;
    const target = p.owner === "player" ? enemy : player;
    const hit = { x: p.x - p.radius, y: p.y - p.radius, w: p.radius * 2, h: p.radius * 2 };
    if (p.life > 0 && laneClose({ lane: p.lane }, target, 34) && rectsOverlap(hit, bodyRect(target))) {
      p.life = 0;
      damageFighter(p.owner === "player" ? player : enemy, target, p.damage, 290);
    }
  });
  projectiles = projectiles.filter((p) => p.life > 0 && p.x > -40 && p.x < canvas.width + 40);
}

function burst(x, y, color, count) {
  for (let i = 0; i < count; i += 1) {
    particles.push({
      x,
      y,
      vx: (Math.random() - 0.5) * 420,
      vy: (Math.random() - 0.9) * 320,
      life: 0.34 + Math.random() * 0.26,
      color,
    });
  }
}

function endMatch(title, text) {
  if (matchOver) return;
  matchOver = true;
  bannerTitle.textContent = title;
  bannerText.textContent = `${text} · \u70b9\u51fb\u91cd\u65b0\u5f00\u59cb`;
  banner.classList.remove("hidden");
}

function updateParticles(dt) {
  particles.forEach((p) => {
    p.life -= dt;
    p.vy += 720 * dt;
    p.x += p.vx * dt;
    p.y += p.vy * dt;
  });
  particles = particles.filter((p) => p.life > 0);
  flashes.forEach((f) => {
    f.life -= dt;
    f.radius += 980 * dt;
  });
  flashes = flashes.filter((f) => f.life > 0);
}

function drawStreet() {
  if (stagePreview.complete && stagePreview.naturalWidth) {
    ctx.imageSmoothingEnabled = false;
    const scale = Math.max(canvas.width / stagePreview.naturalWidth, canvas.height / stagePreview.naturalHeight);
    const w = stagePreview.naturalWidth * scale;
    const h = stagePreview.naturalHeight * scale;
    ctx.drawImage(stagePreview, (canvas.width - w) / 2, canvas.height - h, w, h);
    ctx.fillStyle = "rgba(0,0,0,0.12)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    return;
  }

  const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
  g.addColorStop(0, "#172128");
  g.addColorStop(0.52, "#2b2927");
  g.addColorStop(0.53, "#171311");
  g.addColorStop(1, "#080706");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = "#24313a";
  for (let i = 0; i < 9; i += 1) {
    const x = i * 118 - 28;
    const h = 138 + (i % 3) * 48;
    ctx.fillRect(x, 236 - h, 90, h);
    ctx.fillStyle = i % 2 ? "#e2a943" : "#3a8a9b";
    for (let y = 122 - h; y < 210; y += 32) ctx.fillRect(x + 16, y, 12, 16);
    ctx.fillStyle = "#24313a";
  }

  ctx.fillStyle = "#111";
  ctx.fillRect(0, 282, canvas.width, 182);
  ctx.strokeStyle = "rgba(247,238,225,0.22)";
  ctx.lineWidth = 5;
  ctx.setLineDash([52, 42]);
  for (let y = 332; y <= 428; y += 48) {
    ctx.beginPath();
    ctx.moveTo(30, y);
    ctx.lineTo(canvas.width - 30, y);
    ctx.stroke();
  }
  ctx.setLineDash([]);

  ctx.fillStyle = "#2f241f";
  ctx.fillRect(0, 464, canvas.width, canvas.height - 464);
  ctx.fillStyle = "rgba(247,238,225,0.12)";
  for (let x = 0; x < canvas.width; x += 96) ctx.fillRect(x, 492, 54, 4);
}

function drawFighter(f) {
  if (drawSpriteFighter(f)) return;

  const y = footY(f);
  const lean = f.vx * 0.025;

  ctx.save();
  ctx.translate(f.x, y);
  ctx.scale(renderScaleX(f), 1);
  ctx.rotate(lean * 0.01);

  ctx.fillStyle = "rgba(0,0,0,0.35)";
  ctx.beginPath();
  ctx.ellipse(0, 8 + f.jump * 0.12, 44, 12, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.lineWidth = 16;
  ctx.lineCap = "round";
  ctx.strokeStyle = "#1a1110";
  ctx.beginPath();
  ctx.moveTo(-12, -62);
  ctx.lineTo(-25, -6);
  ctx.moveTo(14, -62);
  ctx.lineTo(26, -4);
  ctx.stroke();

  ctx.strokeStyle = f.color;
  ctx.lineWidth = 22;
  ctx.beginPath();
  ctx.moveTo(0, -112);
  ctx.lineTo(0, -48);
  ctx.stroke();

  ctx.strokeStyle = f.trim;
  ctx.lineWidth = f.attack && f.attack.kind === "heavy" ? 20 : f.attack ? 17 : 14;
  ctx.beginPath();
  ctx.moveTo(0, -100);
  if (f.block) {
    ctx.lineTo(28, -118);
  } else if (f.attack) {
    const reach = f.attack.kind === "heavy" ? 92 : f.attack.kind === "dash" ? 86 : 66;
    const y = f.attack.kind === "heavy" ? -92 : -104;
    ctx.lineTo(reach, y);
  } else {
    ctx.lineTo(38, -80);
  }
  ctx.moveTo(-4, -94);
  ctx.lineTo(-35, -72);
  ctx.stroke();

  if (f.block) {
    ctx.strokeStyle = "rgba(124,199,232,0.82)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(34, -100, 34, -1.25, 1.25);
    ctx.stroke();
  }

  ctx.fillStyle = f.trim;
  ctx.fillRect(-23, -90, 46, 18);
  ctx.fillStyle = "#251917";
  ctx.beginPath();
  ctx.arc(0, -135, 25, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = f.trim;
  ctx.fillRect(6, -142, 15, 6);
  ctx.restore();
}

function stateFor(f) {
  const now = performance.now();
  let wanted = "idle";
  if (f.hitStun > 0) wanted = "hurt";
  else if (!f.grounded) wanted = f.name === "player" ? "jump" : "idle";
  else if (f.attack) wanted = f.attack.kind === "normal" ? "jab" : "punch";
  else if (Math.abs(f.vx) > 26 || Math.abs(f.vlane) > 24) wanted = "walk";

  const locked = now - f.animChangedAt < 120 && ["jab", "punch", "hurt"].includes(f.animState);
  if (!locked && wanted !== f.animState) {
    f.animState = wanted;
    f.animChangedAt = now;
  }
  return f.animState;
}

function drawSpriteFighter(f) {
  const state = stateFor(f);
  const pack = sprites[f.name];
  const anim = pack[state] || pack.idle;
  const fps = state === "idle" ? 6 : state === "walk" ? 10 : 9;
  const frame = Math.floor((performance.now() - f.animChangedAt) / (1000 / fps)) % anim.length;
  const img = anim[frame] || anim[0];
  if (!img.complete || !img.naturalWidth) return false;

  const y = footY(f);
  const scale = f.name === "player" ? 3 : 3;
  const drawW = Math.round(img.naturalWidth * scale);
  const drawH = Math.round(img.naturalHeight * scale);
  const drawX = -Math.round(drawW / 2);
  const drawY = -drawH + 6;

  ctx.save();
  ctx.imageSmoothingEnabled = false;
  ctx.globalAlpha = 0.36;
  if (shadowImage.complete && shadowImage.naturalWidth) {
    ctx.drawImage(shadowImage, f.x - 35, y - 3, 70, 22);
  } else {
    ctx.fillStyle = "black";
    ctx.beginPath();
    ctx.ellipse(f.x, y + 8, 40, 12, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  ctx.translate(f.x, y);
  ctx.scale(renderScaleX(f), 1);
  ctx.drawImage(img, drawX, drawY, drawW, drawH);

  if (f.block) {
    ctx.strokeStyle = "rgba(124,199,232,0.82)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(32, -82, 34, -1.25, 1.25);
    ctx.stroke();
  }
  ctx.restore();
  return true;
}

function drawEffects() {
  projectiles.forEach((p) => {
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.55)";
    ctx.lineWidth = 3;
    ctx.stroke();
  });

  flashes.forEach((f) => {
    ctx.globalAlpha = clamp(f.life * 2.2, 0, 0.7);
    ctx.strokeStyle = f.color;
    ctx.lineWidth = 12;
    ctx.beginPath();
    ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 1;
  });

  particles.forEach((p) => {
    ctx.globalAlpha = clamp(p.life * 2.5, 0, 1);
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x, p.y, 6, 6);
    ctx.globalAlpha = 1;
  });
}

function drawSkillText(f, x, align) {
  ctx.save();
  ctx.textAlign = align;
  ctx.font = "bold 13px Trebuchet MS, sans-serif";
  ctx.fillStyle = "rgba(247,238,225,0.9)";
  const values = [
    `J/K ${f.attackCd > 0 ? f.attackCd.toFixed(1) : "READY"}`,
    `L ${f.block ? "BLOCK" : "GUARD"}`,
    `U ${f.skillCd.dash > 0 ? f.skillCd.dash.toFixed(1) : "READY"}`,
    `I ${f.skillCd.wave > 0 ? f.skillCd.wave.toFixed(1) : "READY"}`,
    `O ${f.energy >= 100 && f.skillCd.ult <= 0 ? "ULT" : Math.floor(f.energy)}`,
  ];
  ctx.fillText(values.join("   "), x, 28);
  ctx.restore();
}

function draw() {
  ctx.save();
  if (shake > 0) {
    ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
    shake *= 0.84;
  }
  drawStreet();
  const fighters = [player, enemy].sort((a, b) => footY(a) - footY(b));
  fighters.forEach(drawFighter);
  drawEffects();
  drawSkillText(player, 18, "left");
  ctx.restore();
}

function update(dt) {
  if (!matchOver) {
    timeLeft -= dt;
    if (timeLeft <= 0) {
      const title = player.health === enemy.health ? "\u5e73\u5c40" : player.health > enemy.health ? "\u80dc\u5229" : "\u5931\u8d25";
      endMatch(title, "\u65f6\u95f4\u7ed3\u675f");
    }
  }
  updateFighter(player, enemy, dt);
  updateFighter(enemy, player, dt);
  resolveMelee(player, enemy);
  resolveMelee(enemy, player);
  updateProjectiles(dt);
  updateParticles(dt);
  playerHealthEl.style.width = `${player.health}%`;
  enemyHealthEl.style.width = `${enemy.health}%`;
  playerEnergyEl.style.width = `${player.energy}%`;
  enemyEnergyEl.style.width = `${enemy.energy}%`;
  timerText.textContent = String(Math.max(0, Math.ceil(timeLeft)));
}

function loop(now) {
  const dt = Math.min(0.033, (now - last) / 1000 || 0);
  last = now;
  update(dt);
  draw();
  requestAnimationFrame(loop);
}

window.addEventListener("keydown", (event) => {
  const key = event.key.toLowerCase();
  keys.add(key);
  if (key === " ") jump(player);
  if (key === "j") startAttack(player, "normal");
  if (key === "k") startAttack(player, "heavy");
  if (key === "u") useDash(player);
  if (key === "i") useWave(player);
  if (key === "o") useUltimate(player, enemy);
  if ([" ", "w", "a", "s", "d", "j", "k", "l", "u", "i", "o", "arrowleft", "arrowright", "arrowup", "arrowdown"].includes(key)) event.preventDefault();
});

window.addEventListener("keyup", (event) => {
  keys.delete(event.key.toLowerCase());
});

restartBtn.addEventListener("click", resetGame);
banner.addEventListener("click", resetGame);

resetGame();
requestAnimationFrame(loop);
