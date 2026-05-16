import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print(json.dumps({"ok": False, "error": f"Playwright not available: {e}"}, ensure_ascii=False, indent=2))
    sys.exit(2)


def parse_args():
    p = argparse.ArgumentParser(description="Auto debug Bug #2: bid/pass verify failure")
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--headless", action="store_true", default=True)
    return p.parse_args()


def wait_page_active(page, page_id, timeout_ms=10000):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        active = page.evaluate(
            "(pid) => !!document.getElementById(pid)?.classList.contains('active')",
            page_id,
        )
        if active:
            return True
        page.wait_for_timeout(120)
    return False


def run():
    args = parse_args()
    repo = Path(__file__).resolve().parent
    server = None
    ts = int(time.time())
    mssv = f"E2E{ts % 1000000}"
    name = f"E2E User {ts % 10000}"
    email = f"e2e_{ts}@example.com"
    password = "1234"
    team = f"E2E TEAM {ts % 1000}"

    result = {
        "ok": True,
        "iterations": args.iterations,
        "mssv": mssv,
        "team": team,
        "steps": [],
        "failures": [],
    }

    def step(name, ok=True, detail=None):
        result["steps"].append({"step": name, "ok": ok, "detail": detail})
        if not ok:
            result["ok"] = False

    try:
        server = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(args.port), "--bind", "127.0.0.1"],
            cwd=str(repo),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)

        url = f"http://127.0.0.1:{args.port}/index.html"

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=args.headless)
            admin_ctx = browser.new_context()
            user_ctx = browser.new_context()
            admin = admin_ctx.new_page()
            user = user_ctx.new_page()

            for pg in (admin, user):
                pg.on("dialog", lambda d: d.accept())

            admin.goto(url, wait_until="domcontentloaded", timeout=30000)
            user.goto(url, wait_until="domcontentloaded", timeout=30000)
            admin.wait_for_timeout(2500)
            user.wait_for_timeout(2500)

            # Admin login
            admin.evaluate("showPage('page-login')")
            admin.fill("#login-username", "admin@ussc-chess.com")
            admin.fill("#login-password", "admin123")
            admin.evaluate("handleAdminLogin()")
            admin.wait_for_timeout(3500)
            admin_ok = wait_page_active(admin, "page-admin")
            step("admin_login", admin_ok)
            if not admin_ok:
                raise RuntimeError("Admin login failed")

            # User register (if already exists, continue to login)
            user.evaluate("showPage('page-account-register')")
            user.fill("#acc-reg-mssv", mssv)
            user.fill("#acc-reg-name", name)
            user.fill("#acc-reg-email", email)
            user.fill("#acc-reg-password", password)
            user.fill("#acc-reg-confirm", password)
            user.evaluate("handleAccountRegister()")
            user.wait_for_timeout(2000)
            step("user_register_attempt", True)

            # User login
            user.evaluate("showPage('page-account-login')")
            user.fill("#acc-login-mssv", mssv)
            user.fill("#acc-login-password", password)
            user.evaluate("handleAccountLogin()")
            user.wait_for_timeout(2500)
            logged_in = user.evaluate("sessionStorage.getItem('loggedInMssv')")
            login_ok = logged_in == mssv
            step("user_login", login_ok, {"loggedInMssv": logged_in})
            if not login_ok:
                raise RuntimeError("User login failed")

            # Create team and prep roundData
            admin.evaluate(
                """async ({team,mssv,name}) => {
                    await teamsCollection.doc(team).set({
                      name: team,
                      totalScore: 500,
                      baseScore: 500,
                      auctionScore: 0,
                      correctAnswers: 0,
                      wrongAnswers: 0,
                      members: [{ mssv, id: mssv, name }]
                    }, { merge: true });

                    const snap = await auctionStateDoc.get();
                    const d = snap.exists ? snap.data() : {};
                    const fallbackRounds = [
                      { fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2BPP3/5N2/PPP2PPP/RNBQK2R b KQkq - 2 3', answer: 'Nf6', range: '100–300' },
                      { fen: 'rnbqkb1r/pppp1ppp/5n2/4p3/1P1PP3/5N2/P1P2PPP/RNBQKB1R b KQkq - 0 3', answer: 'Bxb4+', range: '100–300' }
                    ];
                    await auctionStateDoc.set({
                      roundData: Array.isArray(d.roundData) && d.roundData.length >= 2 ? d.roundData : fallbackRounds
                    }, { merge: true });
                }""",
                {"team": team, "mssv": mssv, "name": name},
            )
            admin.wait_for_timeout(1200)
            step("admin_prepare_team_and_rounddata", True)

            # Enter register2 once
            user.evaluate("showPage('page-register2')")
            user.fill("#reg2-team", team)
            user.evaluate("handleRegister2()")
            user.wait_for_timeout(2500)
            entered = wait_page_active(user, "page-auction-player", timeout_ms=8000)
            step("user_enter_auction", entered)
            if not entered:
                raise RuntimeError("User cannot enter auction page")

            for i in range(args.iterations):
                target_round = i % 2

                admin.evaluate(
                    """async ({round}) => {
                        const snap = await auctionStateDoc.get();
                        const d = snap.exists ? snap.data() : {};
                        await auctionStateDoc.set({
                          ...d,
                          round,
                          running: true,
                          review: false,
                          finalized: false,
                          timeLeft: 180,
                          bids: {},
                          answers: {},
                          teamReview: {},
                          finalResults: {}
                        }, { merge: true });
                    }""",
                    {"round": target_round},
                )

                admin.wait_for_timeout(1200)
                user.wait_for_timeout(1200)

                user.evaluate("startAuctionPlayer()")
                user.wait_for_timeout(800)

                do_bid = (i % 2 == 0)
                if do_bid:
                    info = user.evaluate(
                        """() => {
                            const rangeText = document.getElementById('player-bet-range')?.textContent || '100 – 300 ĐP';
                            const nums = (rangeText.match(/\\d+/g) || []).map(v => parseInt(v, 10));
                            const minBet = nums[0] || 100;
                            const amount = Math.max(minBet, 150);
                            const answer = (auctionState?.roundData?.[auctionState.round]?.answer || 'Nf6').toUpperCase();
                            return { amount, answer };
                        }"""
                    )
                    user.fill("#player-bet-input", str(info["amount"]))
                    user.fill("#player-answer-input", info["answer"])
                    user.evaluate("placeAuctionBid()")
                    expected = {"amount": int(info["amount"]), "passed": False}
                else:
                    user.evaluate("passAuctionBid()")
                    expected = {"amount": 0, "passed": True}

                user.wait_for_timeout(4200)

                server_state = admin.evaluate(
                    """async (team) => {
                        const snap = await auctionStateDoc.get();
                        const d = snap.data() || {};
                        return {
                          bid: d.bids?.[team] || null,
                          answer: d.answers?.[team] ?? null,
                          review: d.teamReview?.[team] || null,
                          round: d.round,
                          running: d.running,
                          reviewMode: d.review
                        };
                    }""",
                    team,
                )

                ok = bool(server_state.get("bid")) \
                    and server_state["bid"].get("amount") == expected["amount"] \
                    and bool(server_state["bid"].get("passed")) == expected["passed"]

                step_name = f"iter_{i+1}_{'bid' if do_bid else 'pass'}"
                step(step_name, ok, {"expected": expected, "server": server_state})

                if not ok:
                    debug_user = user.evaluate("""async (mssv) => {
                        try { return await window.debugBidStatus(mssv); }
                        catch (e) { return { error: String(e) }; }
                    }""", mssv)
                    result["failures"].append({
                        "iteration": i + 1,
                        "mode": "bid" if do_bid else "pass",
                        "expected": expected,
                        "server": server_state,
                        "debugUser": debug_user,
                    })
                    break

            browser.close()

    except Exception as e:
        result["ok"] = False
        result["failures"].append({"fatal": str(e)})
    finally:
        if server is not None:
            try:
                server.terminate()
                server.wait(timeout=2)
            except Exception:
                pass

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    run()
