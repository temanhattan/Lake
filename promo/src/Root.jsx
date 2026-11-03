import React from "react";
import { Composition } from "remotion";
import { Promo } from "./Promo";

export function Root() {
  return (
    <Composition
      id="LakePromo"
      component={Promo}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={1560}
      defaultProps={{ language: "en", reducedMotion: false }}
    />
  );
}
