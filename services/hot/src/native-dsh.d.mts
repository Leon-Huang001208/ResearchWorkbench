import type {DshRuntime} from './dsh-text.ts';
export function createNativeDsh(config:{source:string;credentials:{python:string;bridge:string;dataHome:string}}):Promise<{
  runtime:DshRuntime;safeOutput:(text:string)=>boolean;close:()=>Promise<void>
}>;
