import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

type Variant = "hero" | "ambient";

const CREAM = 0xf7f1e4;

function makeRadialTexture(stops: [number, string][], size = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.Texture();
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  for (const [offset, color] of stops) gradient.addColorStop(offset, color);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.wrapS = THREE.ClampToEdgeWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.needsUpdate = true;
  return texture;
}

function useMedia(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const update = () => setMatches(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [query]);
  return matches;
}

function SparkOrbit({ count, radius }: { count: number; radius: number }) {
  const points = useRef<THREE.Points>(null);
  const geometry = useMemo(() => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const a = (i / count) * Math.PI * 2;
      const r = radius + 0.08 * Math.sin(i * 2.1);
      positions[i * 3] = Math.cos(a) * r;
      positions[i * 3 + 1] = Math.sin(a * 2.4) * 0.18;
      positions[i * 3 + 2] = Math.sin(a) * r;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geo;
  }, [count, radius]);

  const sparkMap = useMemo(
    () => makeRadialTexture([
      [0, "rgba(198,255,0,1)"],
      [0.4, "rgba(198,255,0,0.55)"],
      [1, "rgba(198,255,0,0)"],
    ], 64),
    [],
  );

  useEffect(() => () => {
    geometry.dispose();
    sparkMap.dispose();
  }, [geometry, sparkMap]);

  useFrame((_, delta) => {
    if (points.current) points.current.rotation.y += delta * 0.16;
  });

  return (
    <points ref={points} geometry={geometry}>
      <pointsMaterial
        map={sparkMap}
        color="#C6FF00"
        size={0.08}
        sizeAttenuation
        transparent
        opacity={0.9}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function TorusEngine({
  intensity,
  followPointer,
  sparkCount,
  compact,
}: {
  intensity: number;
  followPointer: boolean;
  sparkCount: number;
  compact: boolean;
}) {
  const group = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);
  const pointer = useRef(new THREE.Vector2());

  useEffect(() => {
    if (!followPointer) return;
    const onMove = (event: PointerEvent) => {
      pointer.current.set(
        (event.clientX / window.innerWidth) * 2 - 1,
        -(event.clientY / window.innerHeight) * 2 + 1,
      );
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
  }, [followPointer]);

  useFrame((state, delta) => {
    if (!group.current) return;
    group.current.rotation.y += delta * 0.12 * intensity;
    if (followPointer) {
      group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, 0.2 + pointer.current.y * 0.12, 0.04);
      group.current.rotation.z = THREE.MathUtils.lerp(group.current.rotation.z, pointer.current.x * 0.08, 0.04);
    }
    group.current.position.y = Math.sin(state.clock.elapsedTime * 0.4) * 0.03 * intensity;
    if (ring.current) ring.current.rotation.y -= delta * 0.28 * intensity;
  });

  return (
    <group ref={group} rotation={[0.2, 0.55, 0]} scale={compact ? 0.72 : 1}>
      <mesh rotation={[Math.PI / 2.35, 0, 0]}>
        <torusGeometry args={compact ? [1.12, 0.38, 32, 96] : [1.12, 0.38, 64, 180]} />
        {compact ? (
          <meshStandardMaterial
            color="#FF5A36"
            metalness={0.18}
            roughness={0.2}
            emissive="#7A180C"
            emissiveIntensity={0.12}
          />
        ) : (
          <meshPhysicalMaterial
            color="#FF5A36"
            metalness={0.16}
            roughness={0.14}
            clearcoat={1}
            clearcoatRoughness={0.1}
            sheen={0.35}
            sheenColor="#FFB199"
            emissive="#7A180C"
            emissiveIntensity={0.14}
          />
        )}
      </mesh>
      <mesh ref={ring} rotation={[Math.PI / 2.2, 0.35, 0.2]}>
        <torusGeometry args={compact ? [1.58, 0.028, 8, 80] : [1.58, 0.028, 12, 140]} />
        <meshBasicMaterial color="#C6FF00" transparent opacity={0.92} />
      </mesh>
      {sparkCount > 0 ? <SparkOrbit count={sparkCount} radius={compact ? 1.68 : 1.85} /> : null}
    </group>
  );
}

export function OrbitScene({ variant = "hero" }: { variant?: Variant }) {
  const hero = variant === "hero";
  const reduced = useMedia("(prefers-reduced-motion: reduce)");
  const compact = useMedia("(max-width: 767px), (pointer: coarse)");
  const finePointer = useMedia("(hover: hover) and (pointer: fine)");

  const intensity = reduced ? 0 : hero ? 1 : 0.35;
  const sparkCount = reduced ? 0 : compact ? 24 : hero ? 90 : 48;

  return (
    <Canvas
      camera={{
        position: hero ? (compact ? [0, 0.06, 5.6] : [0.12, 0.22, 4.6]) : [1.4, 0.28, 5.6],
        fov: compact ? 30 : 34,
      }}
      dpr={compact ? [1, 1.25] : [1, 1.5]}
      gl={{
        antialias: true,
        alpha: true,
        premultipliedAlpha: true,
        powerPreference: compact ? "low-power" : "high-performance",
        stencil: false,
      }}
      style={{ width: "100%", height: "100%", display: "block", background: "transparent" }}
      onCreated={({ gl }) => {
        gl.setClearColor(CREAM, 0);
        gl.toneMapping = compact ? THREE.NoToneMapping : THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.04;
        gl.outputColorSpace = THREE.SRGBColorSpace;
      }}
    >
      <ambientLight intensity={0.82} />
      <hemisphereLight args={["#FFF8EC", "#C4B49A", 0.55]} />
      <spotLight position={[3.2, 5.2, 4]} intensity={compact ? 36 : 52} angle={0.44} penumbra={0.92} color="#fff6ea" />
      <pointLight position={[-2.2, 1.1, 2.6]} intensity={compact ? 5 : 7} color="#FF8A70" />
      <TorusEngine
        intensity={intensity}
        followPointer={hero && finePointer && !reduced}
        sparkCount={sparkCount}
        compact={compact}
      />
    </Canvas>
  );
}
