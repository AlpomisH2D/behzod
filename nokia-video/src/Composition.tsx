import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { useVideoConfig } from "remotion";
import { Scene1, Scene2, Scene3, Scene4, Scene5 } from "./ScenesA";
import { Scene6, Scene7, Scene8, Scene9, Scene10 } from "./ScenesB";
import { DUR, TRANSITION_FRAMES } from "./timing";

const SCENES = [Scene1, Scene2, Scene3, Scene4, Scene5, Scene6, Scene7, Scene8, Scene9, Scene10];
const NAMES = ["Hook", "Arxiv 1865", "Finlyandiya", "Tegirmon", "Nokia shaharchasi", "Konveyer", "Xelsinki-Moskva", "2007 ulushi", "Sotildi", "Savol"];

export const totalFrames = (fps: number) =>
  DUR.reduce((s, d) => s + Math.round(d * fps), 0) - (DUR.length - 1) * TRANSITION_FRAMES;

export const NokiaVideo: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <TransitionSeries>
      {SCENES.flatMap((Scene, i) => {
        const nodes = [
          <TransitionSeries.Sequence
            key={`s${i}`}
            name={NAMES[i]}
            durationInFrames={Math.round(DUR[i] * fps)}
            premountFor={fps}
          >
            <Scene />
          </TransitionSeries.Sequence>,
        ];
        if (i < SCENES.length - 1) {
          nodes.push(
            <TransitionSeries.Transition
              key={`t${i}`}
              presentation={slide({ direction: i % 2 === 0 ? "from-right" : "from-bottom" })}
              timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
            />,
          );
        }
        return nodes;
      })}
    </TransitionSeries>
  );
};
