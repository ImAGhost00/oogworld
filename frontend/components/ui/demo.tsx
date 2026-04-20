import { Particles } from "@/components/ui/particles";

const Demo = () => {
  return (
    <div className="relative h-screen w-full overflow-hidden">
      <div className="absolute inset-0 z-0">
        <Particles quantity={300} className="h-full w-full" color="#000000" />
      </div>
      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center z-10 text-3xl font-semibold tracking-tight">
        HextaUI
      </div>
    </div>
  );
};

export { Demo };
export default Demo;
