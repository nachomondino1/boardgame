/* Binario mínimo para el LaunchAgent (~/Library/LaunchAgents/com.nachomondino.boardgame-sync.plist).
 *
 * Por qué existe: launchd no puede ejecutar cron_sync_data.sh directo
 * porque toca ~/Documents/GitHub/boardgame, carpeta protegida por macOS
 * (TCC) para procesos en background — necesita Full Disk Access. Dárselo
 * a /bin/bash (el intérprete de CUALQUIER script shell del sistema) es
 * mucho más amplio de lo necesario. Este binario compilado y propio es el
 * único al que se le da ese permiso: el acceso queda acotado a esta
 * automatización puntual, no a bash en general.
 *
 * Compilar (ya compilado en ~/cronjobs/boardgame-sync/, no hace falta
 * recompilar salvo que cambie este archivo):
 *   clang -O2 -o ~/cronjobs/boardgame-sync/boardgame-sync-launcher scripts/sync_launcher.c
 *
 * Si se recompila, hay que volver a agregar el binario a Full Disk Access
 * (System Settings → Privacy & Security) — macOS lo trata como un archivo
 * nuevo aunque el path no cambie.
 */
#include <unistd.h>

int main(void) {
    execl("/bin/bash", "bash",
          "/Users/nachomondino/Documents/GitHub/boardgame/scripts/cron_sync_data.sh",
          (char *)NULL);
    return 1; /* solo se llega acá si execl falla */
}
