// Royals Auction Arena - animated 3D cricket ground for the home page.
// Self-contained Three.js scene, loaded as an ES module from the site's own files.
import * as THREE from './lib/three.module.min.js';

const PINK = 0xeb007e;
const NAVY = 0x16265e;
const CHAMPAGNE = 0xf4cfa3;

function stripeTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  const greens = ['#4e9e4a', '#458f42'];
  for (let i = 14; i > 0; i--) {
    g.beginPath();
    g.arc(256, 256, i * 19, 0, Math.PI * 2);
    g.fillStyle = greens[i % 2];
    g.fill();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function makeStumps(mats) {
  const group = new THREE.Group();
  const geo = new THREE.CylinderGeometry(0.09, 0.09, 0.72, 10);
  [-0.16, 0, 0.16].forEach(x => {
    const s = new THREE.Mesh(geo, mats.stump);
    s.position.set(x, 0.36, 0);
    s.castShadow = true;
    group.add(s);
  });
  const bailGeo = new THREE.CylinderGeometry(0.035, 0.035, 0.2, 8);
  [-0.08, 0.08].forEach(x => {
    const b = new THREE.Mesh(bailGeo, mats.stump);
    b.rotation.z = Math.PI / 2;
    b.position.set(x, 0.74, 0);
    group.add(b);
  });
  return group;
}

function makePlayer(mats, shirt) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.45, 1.1, 6, 12), shirt);
  body.position.y = 1.05;
  body.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.3, 14, 12), mats.skin);
  head.position.y = 2.25;
  head.castShadow = true;
  g.add(body, head);
  return g;
}

export function initGround3D(canvas, stage) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (err) {
    return null;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0xeef1fa, 120, 220);

  const camera = new THREE.PerspectiveCamera(42, 2, 0.1, 500);

  const hemi = new THREE.HemisphereLight(0xeaf0ff, 0x3f7a3f, 0.95);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xfff4e0, 1.6);
  sun.position.set(45, 70, 25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -75; sun.shadow.camera.right = 75;
  sun.shadow.camera.top = 75; sun.shadow.camera.bottom = -75;
  sun.shadow.camera.far = 200;
  sun.shadow.bias = -0.0004;
  scene.add(sun);

  const mats = {
    pitch: new THREE.MeshStandardMaterial({ color: 0xd9c29a, roughness: 0.95 }),
    crease: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.8 }),
    stump: new THREE.MeshStandardMaterial({ color: CHAMPAGNE, roughness: 0.5 }),
    rope: new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.7 }),
    pink: new THREE.MeshStandardMaterial({ color: PINK, roughness: 0.55 }),
    navy: new THREE.MeshStandardMaterial({ color: NAVY, roughness: 0.55 }),
    ball: new THREE.MeshStandardMaterial({ color: 0xc2142f, roughness: 0.35 }),
    skin: new THREE.MeshStandardMaterial({ color: 0xc98d64, roughness: 0.7 }),
    shirtPink: new THREE.MeshStandardMaterial({ color: PINK, roughness: 0.6 }),
    shirtNavy: new THREE.MeshStandardMaterial({ color: 0x24408f, roughness: 0.6 }),
    stand: new THREE.MeshStandardMaterial({ color: 0x1c2c66, roughness: 0.9 }),
    metal: new THREE.MeshStandardMaterial({ color: 0x9aa4bd, roughness: 0.4, metalness: 0.5 }),
    lampOn: new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff2c9, emissiveIntensity: 0.9 })
  };

  // Outfield with mow stripes
  const field = new THREE.Mesh(new THREE.CircleGeometry(62, 72), new THREE.MeshStandardMaterial({ map: stripeTexture(), roughness: 1 }));
  field.rotation.x = -Math.PI / 2;
  field.receiveShadow = true;
  scene.add(field);

  // Spectator stand ring and boundary rope
  const stand = new THREE.Mesh(new THREE.RingGeometry(65, 78, 72), mats.stand);
  stand.rotation.x = -Math.PI / 2;
  stand.position.y = 0.05;
  scene.add(stand);
  const rope = new THREE.Mesh(new THREE.TorusGeometry(58, 0.35, 10, 90), mats.rope);
  rope.rotation.x = Math.PI / 2;
  rope.position.y = 0.15;
  scene.add(rope);

  // Advertising boards, alternating Royals pink and navy
  const boardGeo = new THREE.BoxGeometry(9.5, 2.6, 0.4);
  for (let i = 0; i < 22; i++) {
    const a = (i / 22) * Math.PI * 2;
    const board = new THREE.Mesh(boardGeo, i % 2 ? mats.navy : mats.pink);
    board.position.set(Math.cos(a) * 63, 1.3, Math.sin(a) * 63);
    board.lookAt(0, 1.3, 0);
    board.castShadow = true;
    scene.add(board);
  }

  // Pitch strip with crease lines
  const pitch = new THREE.Mesh(new THREE.BoxGeometry(3.05, 0.08, 20.12), mats.pitch);
  pitch.position.y = 0.04;
  pitch.receiveShadow = true;
  scene.add(pitch);
  const creaseGeo = new THREE.BoxGeometry(2.6, 0.02, 0.12);
  [8.9, 7.7, -7.7, -8.9].forEach(z => {
    const c = new THREE.Mesh(creaseGeo, mats.crease);
    c.position.set(0, 0.09, z);
    scene.add(c);
  });

  // Stumps at both ends
  const stumpsA = makeStumps(mats); stumpsA.position.z = -8.2; scene.add(stumpsA);
  const stumpsB = makeStumps(mats); stumpsB.position.z = 8.2; scene.add(stumpsB);

  // Batsman with a bat, bowler, wicketkeeper and fielders
  const batsman = makePlayer(mats, mats.shirtPink);
  batsman.position.set(0.9, 0, -7.4);
  scene.add(batsman);
  const bat = new THREE.Mesh(new THREE.BoxGeometry(0.28, 1.15, 0.12), new THREE.MeshStandardMaterial({ color: 0xe8d5b0, roughness: 0.6 }));
  bat.castShadow = true;
  const batPivot = new THREE.Group();
  batPivot.position.set(0.35, 1.35, -7.1);
  bat.position.y = -0.55;
  batPivot.add(bat);
  batPivot.rotation.x = 0.5;
  scene.add(batPivot);

  const bowler = makePlayer(mats, mats.shirtNavy);
  bowler.position.set(0.4, 0, 11);
  scene.add(bowler);
  const keeper = makePlayer(mats, mats.shirtPink);
  keeper.position.set(0, 0, -10.6);
  keeper.scale.setScalar(0.92);
  scene.add(keeper);
  const fielderSpots = [[18, 10], [-22, 6], [-14, -22], [12, -25], [30, -8], [-30, 18], [4, 30]];
  for (const [x, z] of fielderSpots) {
    const f = makePlayer(mats, mats.shirtNavy);
    f.position.set(x, 0, z);
    f.lookAt(0, 0, 0);
    scene.add(f);
  }

  // Floodlight towers on the four diagonals
  const poleGeo = new THREE.CylinderGeometry(0.35, 0.5, 26, 10);
  const headGeo = new THREE.BoxGeometry(4.4, 2.6, 0.5);
  for (const [x, z] of [[52, 52], [-52, 52], [52, -52], [-52, -52]]) {
    const pole = new THREE.Mesh(poleGeo, mats.metal);
    pole.position.set(x, 13, z);
    pole.castShadow = true;
    const head = new THREE.Mesh(headGeo, mats.lampOn);
    head.position.set(x, 26.5, z);
    head.lookAt(0, 4, 0);
    scene.add(pole, head);
  }

  // The ball
  const ball = new THREE.Mesh(new THREE.SphereGeometry(0.42, 18, 14), mats.ball);
  ball.castShadow = true;
  scene.add(ball);

  // Camera orbit with drag-to-look
  let azimuth = 0.6, dragOffset = 0, elevation = 0.52, dragging = false, lastX = 0, lastY = 0, idleAt = 0;
  stage.addEventListener('pointerdown', e => { dragging = true; lastX = e.clientX; lastY = e.clientY; stage.setPointerCapture(e.pointerId); });
  stage.addEventListener('pointermove', e => {
    if (!dragging) return;
    dragOffset -= (e.clientX - lastX) * 0.006;
    elevation = Math.min(0.95, Math.max(0.18, elevation + (e.clientY - lastY) * 0.004));
    lastX = e.clientX; lastY = e.clientY;
  });
  const endDrag = () => { if (dragging) { dragging = false; idleAt = performance.now(); } };
  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);

  // Delivery-and-shot ball animation loop (seconds)
  const HIT_FROM = new THREE.Vector3(0.35, 1.2, -6.9);
  const HIT_MID = new THREE.Vector3(14, 17, 6);
  const HIT_TO = new THREE.Vector3(30, 0.4, 20);
  const ROLL_TO = new THREE.Vector3(45, 0.4, 30);
  function ballAt(t, T) {
    if (t < T.bounce) { // flight to the bounce
      const u = t / T.bounce;
      ball.position.set(0.15, 1.9 - 1.9 * u * u, 8.4 + (-2.2 - 8.4) * u);
    } else if (t < T.contact) { // up to the bat after the bounce
      const u = (t - T.bounce) / (T.contact - T.bounce);
      ball.position.set(0.25, 0.42 + 0.85 * u, -2.2 + (-6.9 + 2.2) * u);
    } else if (t < T.land) { // the lofted shot
      const u = (t - T.contact) / (T.land - T.contact);
      const a = HIT_FROM.clone().lerp(HIT_MID, u), b = HIT_MID.clone().lerp(HIT_TO, u);
      ball.position.copy(a.lerp(b, u));
    } else if (t < T.rest) { // roll to the rope
      const u = Math.min(1, (t - T.land) / (T.rest - T.land));
      ball.position.copy(HIT_TO).lerp(ROLL_TO, u * (2 - u));
    }
  }
  const T = { bounce: 0.9, contact: 1.5, land: 2.9, rest: 3.7, loop: 4.6 };

  let running = true, raf = 0;
  const clock = new THREE.Clock();
  function frame() {
    raf = requestAnimationFrame(frame);
    if (!running) return;
    const dt = Math.min(clock.getDelta(), 0.05);
    const t = clock.elapsedTime % T.loop;
    ballAt(t, T);
    // bat swing at contact
    const swing = t > T.contact - 0.12 && t < T.contact + 0.45 ? Math.sin((t - (T.contact - 0.12)) / 0.57 * Math.PI) : 0;
    batPivot.rotation.x = 0.5 - swing * 1.9;
    batPivot.rotation.y = swing * 0.5;
    // bowler rocks before the delivery
    bowler.position.z = 11 - Math.min(1, t / T.bounce) * 2.4;
    bowler.rotation.x = t < T.bounce ? Math.sin(t / T.bounce * Math.PI) * 0.25 : 0;
    // slow auto-orbit, paused influence while dragging
    if (!dragging) azimuth += dt * 0.07;
    if (!dragging && performance.now() - idleAt > 2500) dragOffset *= 0.985;
    const az = azimuth + dragOffset;
    const r = 71;
    camera.position.set(Math.sin(az) * r * Math.cos(elevation), r * Math.sin(elevation), Math.cos(az) * r * Math.cos(elevation));
    camera.lookAt(0, 1, 0);
    renderer.render(scene, camera);
  }

  function resize() {
    const w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(stage);
  resize();
  frame();

  const io = new IntersectionObserver(entries => {
    running = entries[0].isIntersecting && !document.hidden && !stage.closest('[hidden]');
    if (running) clock.getDelta();
  }, { threshold: 0.05 });
  io.observe(stage);
  document.addEventListener('visibilitychange', () => { running = !document.hidden; });

  return { renderer, scene };
}

const stage = document.querySelector('.arena3d-stage');
const canvas = document.getElementById('groundCanvas');
if (stage && canvas) {
  const ok = initGround3D(canvas, stage);
  if (!ok) stage.classList.add('no-webgl');
}
