import React from "react";
import { Composition } from "remotion";
import { Promo } from "./Promo";

export function Root() {
  return (
    <>
      <Composition id="LakePromoEN" component={Promo} width={1080} height={1920} fps={30} durationInFrames={1560} defaultProps={{ language: "en", reducedMotion: false }} />
      <Composition id="LakePromoAR" component={Promo} width={1080} height={1920} fps={30} durationInFrames={1560} defaultProps={{ language: "ar", reducedMotion: false }} />
      <Composition id="LakePromo16x9" component={Promo} width={1920} height={1080} fps={30} durationInFrames={1560} defaultProps={{ language: "en", reducedMotion: false }} />
      <Composition id="LakePromoTeaser" component={Promo} width={1080} height={1920} fps={30} durationInFrames={450} defaultProps={{ language: "en", reducedMotion: false }} />
      <Composition id="LakePromoGif" component={Promo} width={360} height={640} fps={15} durationInFrames={225} defaultProps={{ language: "en", reducedMotion: true }} />
    </>
  );
}
