import test from 'node:test';
import assert from 'node:assert/strict';
import {recordingMime,voiceNote} from '../frontend/voice.js';
import {voiceText} from '../frontend/voice-i18n.js';

test('recording chooses a supported format, including Safari MP4',()=>{
 assert.equal(recordingMime({isTypeSupported:type=>type==='audio/mp4'}),'audio/mp4');
 assert.equal(recordingMime({isTypeSupported:()=>false}),'');
});
test('editing a transcript never preserves a misleading speech-rate estimate',()=>{
 const result={text:'Evdə yanğın var.',suggested_type:'fire',speech_seconds:3,words_per_minute:100};
 assert.equal(voiceNote(result,result.text).words_per_minute,100);
 const changed=voiceNote(result,'Başqa cümlə');
 assert.equal(changed.words_per_minute,null);
 assert.equal(changed.speech_seconds,null);
 assert.equal(changed.suggested_type,null);
});
test('voice flow labels are available in all workspace languages',()=>{
 for(const locale of ['az','ru'])assert.deepEqual(Object.keys(voiceText[locale]).sort(),Object.keys(voiceText.en).sort());
});
