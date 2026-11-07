import type {ReactNode} from 'react';
import type {SourceImage} from './source-images';

type Study = {
  date: string;
  series: Map<string, SourceImage[]>;
};

function groupStudies(images: readonly SourceImage[]) {
  const studies = new Map<string, Study>();
  for (const image of images) {
    let study = studies.get(image.study_uid);
    if (!study) {
      study = {date: image.study_date, series: new Map()};
      studies.set(image.study_uid, study);
    }
    const series = study.series.get(image.series_uid);
    if (series) series.push(image);
    else study.series.set(image.series_uid, [image]);
  }
  return studies;
}

export function SourceImageStudies({images, disabled, previewDisabled, onDownload, onPreview, renderPreview}: {
  images: readonly SourceImage[];
  disabled: boolean;
  previewDisabled: boolean;
  onPreview: (image: SourceImage, trigger: HTMLButtonElement) => void;
  renderPreview: (image: SourceImage) => ReactNode;
  onDownload: (image: SourceImage) => void;
}) {
  return <div className="source-image-studies">
    {Array.from(groupStudies(images), ([studyUid, study]) =>
      <section key={studyUid} data-testid="source-image-study" data-study-uid={studyUid}
        aria-label={`Imaging study ${studyUid}`}>
        <h6>Imaging study · <time dateTime={study.date}>{study.date}</time></h6>
        <p className="small">Study UID <code>{studyUid}</code> · {study.series.size} series</p>
        {Array.from(study.series, ([seriesUid, members]) =>
          <details key={seriesUid} open data-testid="source-image-series" data-series-uid={seriesUid}>
            <summary>{members[0].modality} series <code>{seriesUid}</code> · {members.length} linked {members.length === 1 ? 'original' : 'originals'}</summary>
            <ul className="source-image-list">{members.map(image =>
              <li key={image.image_id} data-testid="source-image-row" data-image-id={image.image_id}>
                <p>Instance <code>{image.sop_uid}</code> · {image.byte_count.toLocaleString()} bytes</p>
                <details><summary>Original integrity and identifiers</summary>
                  <dl className="source-metadata">
                    <div><dt>Image</dt><dd><code>{image.image_id}</code></dd></div>
                    <div><dt>Source</dt><dd><code>{image.source_id}</code></dd></div>
                    <div><dt>Original SHA-256</dt><dd><code>{image.sha256}</code></dd></div>
                  </dl>
                </details>
                <div className="actions">
                  {image.modality === 'CT' ? <button type="button" data-testid="source-image-preview-open"
                    aria-label={`View non-diagnostic preview: CT instance ${image.sop_uid}`}
                    disabled={previewDisabled} onClick={event => onPreview(image, event.currentTarget)}>View non-diagnostic preview</button>
                    : <p className="small" data-testid="source-image-preview-unavailable">MR preview is unavailable. The original DICOM can be downloaded.</p>}
                  <button type="button" data-testid="source-image-download" disabled={disabled}
                    aria-label={`Recheck and download original DICOM: ${image.modality} instance ${image.sop_uid}`}
                    onClick={() => onDownload(image)}>Recheck and download original DICOM</button>
                </div>
                {renderPreview(image)}
              </li>)}</ul>
          </details>)}
      </section>)}
  </div>;
}
