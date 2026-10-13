import React from "react";
import { Composition } from "remotion";
import { NokiaVideo, totalFrames } from "./Composition";
import { FPS } from "./timing";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Nokia"
      component={NokiaVideo}
      durationInFrames={totalFrames(FPS)}
      fps={FPS}
      width={1080}
      height={1920}
    />
  );
};
