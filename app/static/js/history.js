/* 결정 이력 화면: 닉네임 저장 (PUT /api/me) */
(function(){
'use strict';
const form = document.getElementById('nickForm');
const toastEl = document.getElementById('toast');
let t;
function toast(msg){
  toastEl.textContent = msg; toastEl.classList.add('show');
  clearTimeout(t); t = setTimeout(() => toastEl.classList.remove('show'), 2000);
}
if(!form) return;
form.addEventListener('submit', async e => {
  e.preventDefault();
  const nickname = document.getElementById('nickname').value;
  try {
    const res = await fetch('/api/me', {
      method: 'PUT', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify({nickname})
    });
    const data = await res.json().catch(() => null);
    if(!res.ok) throw new Error((data && data.error && data.error.message) || '저장하지 못했어요.');
    toast(data.user.nickname ? `닉네임을 ‘${data.user.nickname}’(으)로 저장했어요` : '닉네임을 지웠어요');
  } catch(err){ toast(err.message || '서버에 연결할 수 없어요.'); }
});
})();
