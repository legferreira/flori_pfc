import { initializeApp } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js';
import { getAnalytics, isSupported } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-analytics.js';
import { getAuth } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

const firebaseConfig = {
  apiKey: 'AIzaSyBUV2UafkfRwiIBkFg9OzHvgKPU0KlPg04',
  authDomain: 'flori-1742a.firebaseapp.com',
  projectId: 'flori-1742a',
  storageBucket: 'flori-1742a.firebasestorage.app',
  messagingSenderId: '861010957827',
  appId: '1:861010957827:web:a34517344dd4577c632036',
  measurementId: 'G-GCKL02XF36'
};

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

isSupported()
  .then(suportado => { if (suportado) getAnalytics(app); })
  .catch(() => {});
