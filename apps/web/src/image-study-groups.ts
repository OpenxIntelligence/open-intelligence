import type {SourceImage} from './source-images.js';

export type ImageSeriesGroup=Readonly<{series_uid:string;images:readonly SourceImage[]}>;
export type ImageStudyGroup=Readonly<{study_uid:string;series:readonly ImageSeriesGroup[]}>;

/** Pure presentation projection of a single already-authorized image index.
 * Never treats a series UID as globally unique or reorders the actual originals. */
export function groupSourceImages(images:readonly SourceImage[]):readonly ImageStudyGroup[]{
 const studies=new Map<string,Map<string,SourceImage[]>>();
 for(const image of images){
  let series=studies.get(image.study_uid);
  if(!series){series=new Map();studies.set(image.study_uid,series);}
  let originals=series.get(image.series_uid);
  if(!originals){originals=[];series.set(image.series_uid,originals);}
  originals.push(image);
 }
 return Object.freeze(Array.from(studies,([study_uid,series])=>Object.freeze({
  study_uid,series:Object.freeze(Array.from(series,([series_uid,originals])=>Object.freeze({
   series_uid,images:Object.freeze(originals),
  }))),
 })));
}
