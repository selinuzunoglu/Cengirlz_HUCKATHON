# Enerji Akışı İzleme Sistemi

Bu proje, Valyria gezegenindeki enerji üretim, depolama ve dağıtım süreçlerini gerçek zamanlı izlemek, anomali tespiti yapmak ve verimlilik optimizasyonu sağlamak için FastAPI, Socket.IO, Pandas ve Scikit-learn kullanılarak geliştirilmiştir.

## Kurulum

1. Ortamı oluşturun:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

## Çalıştırma

```bash
uvicorn main:app --reload
``` 