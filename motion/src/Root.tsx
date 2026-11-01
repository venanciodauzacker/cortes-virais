import { CalculateMetadataFunction, Composition } from "remotion";
import { Legendas, LegendasProps } from "./Legendas";

const calculateMetadata: CalculateMetadataFunction<LegendasProps> = ({ props }) => {
  return {
    durationInFrames: Math.max(1, Math.ceil(props.dur * 30)),
    defaultCodec: "prores",
    defaultVideoImageFormat: "png",
    defaultPixelFormat: "yuva444p10le",
    defaultProResProfile: "4444",
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* camada de texto do modelo henrico pro: só a caixa 912x513, fundo transparente */}
      <Composition
        id="Legendas"
        component={Legendas}
        durationInFrames={300}
        fps={30}
        width={912}
        height={513}
        defaultProps={{ dur: 10, els: [], camada: "frente" as const }}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
};
